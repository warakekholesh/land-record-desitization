import os
import json
import uuid
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.conf import settings
from django.db.models import Q
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import LandRecord
from .ocr import run_tesseract_ocr, preprocess_image
from .extraction import extract_land_record_entities
from .validation import validate_land_record
from .sample_generator import create_land_document_image


def user_login(request):
    """Handles user authentication and login."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    next_url = request.GET.get('next') or request.POST.get('next') or 'dashboard'

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = AuthenticationForm()

    return render(request, 'land_records/login.html', {'form': form, 'next': next_url})


def user_logout(request):
    """Logs the user out and redirects to login."""
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')


def user_register(request):
    """Handles new user registration."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Account created successfully! Welcome, {user.username}.")
            return redirect('dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = UserCreationForm()

    return render(request, 'land_records/register.html', {'form': form})


@login_required
def dashboard(request):
    """SIH Dashboard showing high-level stats and recent records."""
    all_records = LandRecord.objects.all()
    total_records = all_records.count()
    consistent_count = all_records.filter(status='consistent').count()
    warning_count = all_records.filter(status='warning').count()
    anomaly_count = all_records.filter(status='anomaly').count()
    available_count = sum(1 for r in all_records if r.effective_ownership_status == 'available')
    owned_count = total_records - available_count
    recent_records = all_records[:8]

    context = {
        'total_records': total_records,
        'consistent_count': consistent_count,
        'warning_count': warning_count,
        'anomaly_count': anomaly_count,
        'available_count': available_count,
        'owned_count': owned_count,
        'recent_records': recent_records,
    }
    return render(request, 'land_records/dashboard.html', context)


@login_required
def upload_record(request):
    """
    Document Upload & Processing View:
    1. Uploads JPG/PNG/PDF or selects preset demo sample
    2. Runs OpenCV preprocessing
    3. Executes Tesseract OCR
    4. Extracts structured entities via Regex/NLP
    5. Runs Rule-Based Anomaly Detection against existing database
    """
    if request.method == 'POST':
        uploaded_file = request.FILES.get('document')
        sample_choice = request.POST.get('sample_choice')

        doc_dir = os.path.join(settings.MEDIA_ROOT, 'documents')
        prep_dir = os.path.join(settings.MEDIA_ROOT, 'preprocessed')
        os.makedirs(doc_dir, exist_ok=True)
        os.makedirs(prep_dir, exist_ok=True)

        unique_id = uuid.uuid4().hex[:8]
        saved_doc_rel_path = ""
        saved_prep_rel_path = ""
        full_doc_path = ""
        full_prep_path = ""

        # Case 1: User uploaded their own file
        if uploaded_file:
            ext = os.path.splitext(uploaded_file.name)[1].lower() or '.png'
            filename = f"upload_{unique_id}{ext}"
            full_doc_path = os.path.join(doc_dir, filename)
            with open(full_doc_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            saved_doc_rel_path = f"documents/{filename}"

        # Case 2: User picked a ready-made SIH demo sample
        elif sample_choice:
            sample_configs = {
                'sample_1': {
                    'survey_no': '101/1', 'owner': 'Rajesh Patil', 'area': '2.5 Hectares',
                    'village': 'Pune', 'taluka': 'Haveli', 'district': 'Pune', 'date': '12/04/2023',
                    'file_tag': '101_1_rajesh_patil'
                },
                'sample_2': {
                    'survey_no': '102/2', 'owner': 'Amit Sharma', 'area': '1.8 Hectares',
                    'village': 'Pune', 'taluka': 'Haveli', 'district': 'Pune', 'date': '15/05/2023',
                    'file_tag': '102_2_amit_sharma'
                },
                'sample_3': {
                    'survey_no': '125/2', 'owner': 'Rajesh Patil', 'area': '2.5 Hectares',
                    'village': 'Pune', 'taluka': 'Haveli', 'district': 'Pune', 'date': '05/08/2022',
                    'file_tag': '125_2_rajesh_patil'
                },
                'sample_4': {
                    'survey_no': '125/2', 'owner': 'Amit Sharma', 'area': '3.7 Hectares',
                    'village': 'Pune', 'taluka': 'Haveli', 'district': 'Pune', 'date': '10/01/2024',
                    'file_tag': '125_2_amit_sharma_conflict'
                },
                'sample_5': {
                    'survey_no': '204/A', 'owner': 'Government Land (Vacant)', 'area': '4.2 Hectares',
                    'village': 'Pune', 'taluka': 'Haveli', 'district': 'Pune', 'date': '20/03/2024',
                    'file_tag': '204_A_vacant_govt_land'
                },
            }
            cfg = sample_configs.get(sample_choice, sample_configs['sample_1'])
            filename = f"sample_{unique_id}_{cfg['file_tag']}.png"
            full_doc_path = os.path.join(doc_dir, filename)
            create_land_document_image(
                output_path=full_doc_path,
                survey_no=cfg['survey_no'],
                owner_name=cfg['owner'],
                area_str=cfg['area'],
                village=cfg['village'],
                taluka=cfg['taluka'],
                district=cfg['district'],
                date_str=cfg['date']
            )
            saved_doc_rel_path = f"documents/{filename}"

        else:
            messages.error(request, "Please choose a file to upload or select a test sample.")
            return render(request, 'land_records/upload.html')

        # Run OpenCV Preprocessing (Grayscale, Blur, Otsu Thresholding)
        prep_filename = f"prep_{os.path.basename(full_doc_path)}.png"
        full_prep_path = os.path.join(prep_dir, prep_filename)
        saved_prep_rel_path = f"preprocessed/{prep_filename}"

        try:
            if not full_doc_path.lower().endswith('.pdf'):
                preprocess_image(full_doc_path, full_prep_path)
            else:
                saved_prep_rel_path = ""
        except Exception as e:
            saved_prep_rel_path = ""

        # Run Tesseract OCR (LSTM)
        ocr_text = run_tesseract_ocr(full_doc_path, full_prep_path if saved_prep_rel_path else None)

        # Run Information Extraction / Rule-Based NER
        extracted = extract_land_record_entities(ocr_text)

        # Build initial record instance
        record = LandRecord(
            document=saved_doc_rel_path,
            preprocessed_image=saved_prep_rel_path if saved_prep_rel_path else None,
            ocr_raw_text=ocr_text,
            owner_name=extracted.get('owner_name') or '',
            survey_number=extracted.get('survey_number') or '',
            area=extracted.get('area'),
            area_unit=extracted.get('area_unit') or 'hectares',
            village=extracted.get('village') or '',
            taluka=extracted.get('taluka') or '',
            district=extracted.get('district') or '',
            record_date=extracted.get('record_date') or '',
        )

        # Auto-classify ownership_status: Empty/Available vs Bought/Owned
        owner_str = (record.owner_name or '').strip().lower()
        if not owner_str or any(w in owner_str for w in ['government', 'govt', 'vacant', 'unassigned', 'empty', 'available']):
            record.ownership_status = 'available'
        else:
            record.ownership_status = 'owned'

        # Run Rule-Based Anomaly Detection against existing records in DB
        existing_records = LandRecord.objects.all()
        status, reasons, conflicts = validate_land_record({
            'survey_number': record.survey_number,
            'owner_name': record.owner_name,
            'area': record.area,
            'village': record.village,
            'taluka': record.taluka,
            'district': record.district,
            'id': None
        }, existing_records=existing_records)

        record.status = status
        record.anomaly_reasons = json.dumps(reasons)
        record.save()

        # Also trigger re-validation for existing records sharing this survey number
        # so existing records reflect new conflicting uploads immediately!
        if record.survey_number:
            related_records = LandRecord.objects.filter(survey_number=record.survey_number).exclude(id=record.id)
            for rel in related_records:
                r_status, r_reasons, _ = validate_land_record({
                    'survey_number': rel.survey_number,
                    'owner_name': rel.owner_name,
                    'area': rel.area,
                    'village': rel.village,
                    'id': rel.id
                }, existing_records=LandRecord.objects.all())
                rel.status = r_status
                rel.anomaly_reasons = json.dumps(r_reasons)
                rel.save()

        messages.success(request, f"Document processed successfully! Result: {record.get_status_display()}")
        return redirect('record_detail', record_id=record.id)

    return render(request, 'land_records/upload.html')


@login_required
def record_list(request):
    """Filterable and searchable Land Records table."""
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    records = LandRecord.objects.all()

    if query:
        records = records.filter(
            Q(survey_number__icontains=query) |
            Q(owner_name__icontains=query) |
            Q(village__icontains=query) |
            Q(district__icontains=query)
        )

    if status_filter in ['consistent', 'warning', 'anomaly']:
        records = records.filter(status=status_filter)

    context = {
        'records': records,
        'query': query,
        'status_filter': status_filter,
    }
    return render(request, 'land_records/records.html', context)


@login_required
def record_detail(request, record_id):
    """Detailed view showing document, OCR text, extracted entities, and anomaly breakdown."""
    record = get_object_or_404(LandRecord, id=record_id)

    # Find conflicting records if any
    conflicting_records = []
    if record.survey_number:
        conflicting_records = LandRecord.objects.filter(
            survey_number=record.survey_number
        ).exclude(id=record.id)

    context = {
        'record': record,
        'conflicting_records': conflicting_records,
    }
    return render(request, 'land_records/record_detail.html', context)


@login_required
def delete_record(request, record_id):
    """Deletes a record and revalidates other records."""
    record = get_object_or_404(LandRecord, id=record_id)
    survey_no = record.survey_number
    record.delete()

    # Revalidate records that shared this survey number
    if survey_no:
        remaining = LandRecord.objects.filter(survey_number=survey_no)
        for rem in remaining:
            r_status, r_reasons, _ = validate_land_record({
                'survey_number': rem.survey_number,
                'owner_name': rem.owner_name,
                'area': rem.area,
                'village': rem.village,
                'id': rem.id
            }, existing_records=LandRecord.objects.all())
            rem.status = r_status
            rem.anomaly_reasons = json.dumps(r_reasons)
            rem.save()

    messages.success(request, "Record deleted successfully.")
    return redirect('record_list')


@login_required
def revalidate_all(request):
    """Runs anomaly detection algorithm across all database records."""
    records = LandRecord.objects.all()
    for rec in records:
        r_status, r_reasons, _ = validate_land_record({
            'survey_number': rec.survey_number,
            'owner_name': rec.owner_name,
            'area': rec.area,
            'village': rec.village,
            'id': rec.id
        }, existing_records=records)
        rec.status = r_status
        rec.anomaly_reasons = json.dumps(r_reasons)
        rec.save()

    messages.success(request, f"Re-validation complete! Analyzed {records.count()} records.")
    return redirect('record_list')


def map_view(request):
    """Renders the Leaflet.js interactive land status map."""
    total_count = LandRecord.objects.count()
    available_count = sum(1 for r in LandRecord.objects.all() if r.effective_ownership_status == 'available')
    owned_count = total_count - available_count

    context = {
        'total_count': total_count,
        'available_count': available_count,
        'owned_count': owned_count,
    }
    return render(request, 'land_records/map.html', context)


def map_data_api(request):
    """
    API view returning all land records and their geospatial coordinates/status.
    Returns JSON with parcel details for Leaflet.js rendering.
    """
    records = LandRecord.objects.all()
    features = []

    # Center reference: Pune / Maharashtra region for SIH demo (18.5204, 73.8567)
    base_lat = 18.5204
    base_lng = 73.8567

    for idx, rec in enumerate(records):
        status_key = rec.effective_ownership_status  # 'available' or 'owned'
        color = '#10b981' if status_key == 'available' else '#ef4444'  # Green vs Red

        # Use actual coordinates if present, else assign deterministic demo coordinates around Pune
        if rec.latitude and rec.longitude:
            lat = float(rec.latitude)
            lng = float(rec.longitude)
        else:
            # Deterministic grid distribution for demo visualization
            row = (idx % 5) - 2
            col = (idx // 5) - 2
            lat = round(base_lat + (row * 0.008) + ((idx * 0.0017) % 0.005), 6)
            lng = round(base_lng + (col * 0.009) + ((idx * 0.0013) % 0.005), 6)

        # Polygon coordinates (if provided as JSON or generate small bounding parcel)
        poly = None
        if rec.polygon_coordinates:
            try:
                poly = json.loads(rec.polygon_coordinates)
            except Exception:
                poly = None

        if not poly:
            delta = 0.002
            poly = [
                [round(lat - delta, 6), round(lng - delta, 6)],
                [round(lat + delta, 6), round(lng - delta, 6)],
                [round(lat + delta, 6), round(lng + delta, 6)],
                [round(lat - delta, 6), round(lng + delta, 6)],
            ]

        features.append({
            'id': rec.id,
            'survey_number': rec.survey_number or f'Survey #{rec.id}',
            'owner_name': rec.owner_name or 'Unassigned / Government',
            'area': rec.area if rec.area is not None else 0.0,
            'area_unit': rec.area_unit or 'hectares',
            'village': rec.village or 'Pune',
            'taluka': rec.taluka or 'Haveli',
            'district': rec.district or 'Pune',
            'record_date': rec.record_date or 'N/A',
            'validation_status': rec.status,
            'validation_label': rec.status_label,
            'anomaly_reasons': rec.anomaly_list,
            'ownership_status': status_key,
            'ownership_label': rec.ownership_label,
            'color': color,
            'latitude': lat,
            'longitude': lng,
            'polygon': poly,
            'detail_url': f'/records/{rec.id}/',
        })

    return JsonResponse({
        'status': 'success',
        'count': len(features),
        'center': [base_lat, base_lng],
        'data': features,
    })


@csrf_exempt
def chatbot_reply(request):
    """
    Land Inquiry Chatbot View:
    Accepts POST request with a user message, checks inquiry keywords
    ('empty land', 'anomaly', '7/12', 'survey number', etc.),
    queries the database for dynamic context, and returns a helpful JSON response.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed.'}, status=405)

    # Parse message from JSON body or POST form data
    user_msg = ''
    try:
        if request.body:
            body_data = json.loads(request.body.decode('utf-8'))
            user_msg = body_data.get('message', '')
    except Exception:
        pass

    if not user_msg:
        user_msg = request.POST.get('message', '')

    msg_clean = user_msg.strip().lower()

    if not msg_clean:
        return JsonResponse({
            'reply': "Please ask a question! You can ask about empty land, anomalies, 7/12 extracts, or specific survey numbers.",
            'suggestions': ["Show empty land", "Check anomalies", "What is 7/12?", "Survey 101/1"]
        })

    # Keyword 1: Empty / Available land
    if any(k in msg_clean for k in ['empty land', 'empty', 'available', 'vacant', 'free land', 'buy land', 'unowned']):
        available_records = [r for r in LandRecord.objects.all() if r.effective_ownership_status == 'available']
        total_avail_area = sum(r.area for r in available_records if r.area)

        if available_records:
            surveys = ", ".join([f"Survey {r.survey_number or r.id}" for r in available_records[:5]])
            reply = (
                f"🟢 <strong>Available Land Parcels Found:</strong><br>"
                f"There are currently <strong>{len(available_records)} empty/available land parcels</strong> in the system "
                f"totaling <strong>{total_avail_area:.2f} hectares</strong>.<br>"
                f"Notable surveys: {surveys}.<br>"
                f"👉 You can visualize these highlighted in <span style='color:#10b981;font-weight:bold;'>GREEN</span> on the <a href='/map/' style='color:#2563eb;text-decoration:underline;'>Interactive Land Map</a>."
            )
        else:
            reply = (
                "ℹ️ Currently, all registered parcels in the system have active owners assigned. "
                "Any unassigned parcels or new government land listings will appear here as 'Empty/Available'."
            )
        suggestions = ["View on Map", "Check anomalies", "What is 7/12?"]

    # Keyword 2: Anomaly / Fraud / Verification
    elif any(k in msg_clean for k in ['anomaly', 'anomalies', 'fraud', 'mismatch', 'verification', 'warning', 'fake', 'conflict']):
        anomalies = LandRecord.objects.filter(status='anomaly')
        warnings = LandRecord.objects.filter(status='warning')
        total_issues = anomalies.count() + warnings.count()

        if total_issues > 0:
            sample_reasons = []
            for rec in anomalies[:3]:
                for r in rec.anomaly_list[:1]:
                    sample_reasons.append(f"• <strong>Survey {rec.survey_number}:</strong> {r}")

            reasons_str = "<br>".join(sample_reasons) if sample_reasons else "Ownership and area cross-validation discrepancies detected."
            reply = (
                f"🚨 <strong>Anomaly Detection Summary:</strong><br>"
                f"We detected <strong>{anomalies.count()} high-risk anomalies</strong> and <strong>{warnings.count()} verification warnings</strong>.<br><br>"
                f"<strong>Recent Flagged Cases:</strong><br>{reasons_str}<br><br>"
                f"Common reasons include mathematical area conflicts, duplicate survey claims, or missing registry stamps."
            )
        else:
            reply = "✅ Great news! All scanned land records currently in the database have passed consistency validation with zero detected anomalies."
        suggestions = ["Show flagged records", "Show empty land", "Explain 7/12"]

    # Keyword 3: 7/12 / Satbara / Extract
    elif any(k in msg_clean for k in ['7/12', '7 12', 'satbara', 'extract', 'what is', 'utara', 'meaning']):
        reply = (
            "📜 <strong>What is a 7/12 (Satbara Utara) Extract?</strong><br>"
            "In Indian land administration (notably Maharashtra & Gujarat), a 7/12 extract is an official revenue document maintained by the Talathi / Revenue Department:<br>"
            "• <strong>Village Form VII (7):</strong> Details land ownership rights, survey/gat numbers, occupant names, and financial liabilities/loans.<br>"
            "• <strong>Village Form XII (12):</strong> Details agricultural use, crop patterns, irrigated vs un-irrigated land, and fallow areas.<br>"
            "Our SIH system automatically uses OCR and NLP to digitize this document, detect mutations, and prevent fraudulent duplicate sales."
        )
        suggestions = ["Show empty land", "Check anomalies", "Upload 7/12 document"]

    # Keyword 4: Survey / Gat Number search
    elif any(k in msg_clean for k in ['survey', 'gat', 'parcel', 'plot', 'number', 'no']):
        match = re.search(r'(\d+(?:/\d+)?)', msg_clean)
        if match:
            search_num = match.group(1)
            matching_records = LandRecord.objects.filter(survey_number__icontains=search_num)
            if matching_records.exists():
                rec = matching_records.first()
                badge = "🟢 Available" if rec.effective_ownership_status == 'available' else "🔴 Bought/Owned"
                reply = (
                    f"📍 <strong>Found Record for Survey #{rec.survey_number}:</strong><br>"
                    f"• <strong>Owner:</strong> {rec.owner_name or 'Unassigned'}<br>"
                    f"• <strong>Area:</strong> {rec.area} {rec.area_unit}<br>"
                    f"• <strong>Location:</strong> {rec.village}, {rec.taluka}, {rec.district}<br>"
                    f"• <strong>Status:</strong> {badge} ({rec.status_label})<br>"
                    f"👉 <a href='/records/{rec.id}/' style='color:#2563eb;text-decoration:underline;'>Click here to view full details & OCR scan</a>"
                )
            else:
                reply = f"🔍 No record found matching Survey Number <strong>{search_num}</strong>. You can upload it via the Upload page or check the record directory."
        else:
            reply = "🔍 Please provide a survey number to search (for example: <em>'Tell me about Survey 101/1'</em> or <em>'Check Gat 125'</em>)."
        suggestions = ["Survey 101/1", "Survey 102/2", "Show empty land"]

    # Keyword 5: Owner / Ownership
    elif any(k in msg_clean for k in ['owner', 'ownership', 'bought', 'owned', 'purchased', 'patil', 'sharma']):
        reply = (
            "👤 <strong>Land Ownership Intelligence:</strong><br>"
            "Our system extracts occupant names from Section 7 of the document. When an owner is registered, the parcel is flagged as "
            "<span style='color:#ef4444;font-weight:bold;'>Bought/Owned (Red)</span>. "
            "Parcels with unassigned owners or government classifications are flagged as "
            "<span style='color:#10b981;font-weight:bold;'>Empty/Available (Green)</span>.<br>"
            "You can click on any parcel on the map to see owner name and survey details."
        )
        suggestions = ["Show empty land", "Open Land Map", "Check anomalies"]

    # Keyword 6: Hello / Help / Greetings
    elif any(k in msg_clean for k in ['hi', 'hello', 'hey', 'help', 'assist', 'who are you', 'how to use']):
        reply = (
            "👋 <strong>Hello! I am your Land Record AI Assistant.</strong><br>"
            "I can assist you with your land queries for the Smart India Hackathon system:<br>"
            "• Ask <em>'Show empty land'</em> to find available plots<br>"
            "• Ask <em>'Check anomalies'</em> to audit potential conflicts or fraud<br>"
            "• Ask <em>'What is 7/12?'</em> to understand extract structures<br>"
            "• Ask <em>'Survey 101/1'</em> to instantly look up a specific plot"
        )
        suggestions = ["Show empty land", "Check anomalies", "What is 7/12?", "Survey 101/1"]

    else:
        reply = (
            f"🤖 I heard: <em>\"{user_msg}\"</em>.<br>"
            "I can help you look up <strong>empty land</strong>, identify <strong>anomalies</strong>, "
            "explain <strong>7/12 extracts</strong>, or search by <strong>Survey Number</strong>.<br>"
            "Try one of the quick suggestions below!"
        )
        suggestions = ["Show empty land", "Check anomalies", "What is 7/12?", "Survey 101/1"]

    return JsonResponse({
        'reply': reply,
        'suggestions': suggestions,
    })


def generate_mock_map_data_view(request):
    """
    Triggers generation of randomized/mock parcel coordinates
    and multi-vertex cadastral boundaries across all database records.
    """
    from django.core.management import call_command
    call_command('generate_mock_map_data')
    messages.success(request, "🎲 Synthetic map coordinates and cadastral boundary polygons successfully generated for all land records!")
    next_url = request.GET.get('next') or 'map_view'
    return redirect(next_url)


