import os
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User
from land_records.models import LandRecord
from land_records.sample_generator import create_land_document_image
from land_records.ocr import run_tesseract_ocr, preprocess_image
from land_records.extraction import extract_land_record_entities
from land_records.validation import validate_land_record


class Command(BaseCommand):
    help = "Seeds sample land records for SIH Hackathon presentation"

    def handle(self, *args, **options):
        # Ensure default demo user exists
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
            self.stdout.write(self.style.SUCCESS("Created demo user: admin / admin123"))

        self.stdout.write("Clearing existing records...")
        LandRecord.objects.all().delete()

        doc_dir = os.path.join(settings.MEDIA_ROOT, 'documents')
        prep_dir = os.path.join(settings.MEDIA_ROOT, 'preprocessed')
        os.makedirs(doc_dir, exist_ok=True)
        os.makedirs(prep_dir, exist_ok=True)

        samples = [
            {
                "filename": "sample_101_1_rajesh_patil.png",
                "survey_no": "101/1",
                "owner": "Rajesh Patil",
                "area_str": "2.5 Hectares",
                "area_val": 2.5,
                "village": "Pune",
                "taluka": "Haveli",
                "district": "Pune",
                "date": "12/04/2023",
                "status": "consistent",
                "reasons": ["Record passed all structural, mathematical, and database consistency validations."]
            },
            {
                "filename": "sample_102_2_amit_sharma.png",
                "survey_no": "102/2",
                "owner": "Amit Sharma",
                "area_str": "1.8 Hectares",
                "area_val": 1.8,
                "village": "Pune",
                "taluka": "Haveli",
                "district": "Pune",
                "date": "15/05/2023",
                "status": "consistent",
                "reasons": ["Record passed all structural, mathematical, and database consistency validations."]
            },
            {
                "filename": "sample_125_2_rajesh_patil.png",
                "survey_no": "125/2",
                "owner": "Rajesh Patil",
                "area_str": "2.5 Hectares",
                "area_val": 2.5,
                "village": "Pune",
                "taluka": "Haveli",
                "district": "Pune",
                "date": "05/08/2022",
                "status": "anomaly",
                "reasons": [
                    "Same Survey Number has conflicting owner and area information.",
                    "Same Survey Number (125/2) is associated with conflicting owner: 'Amit Sharma' vs 'Rajesh Patil'.",
                    "Area mismatch on Survey Number 125/2: 2.5 ha vs 3.7 ha registered under Amit Sharma."
                ]
            },
            {
                "filename": "sample_125_2_amit_sharma_conflict.png",
                "survey_no": "125/2",
                "owner": "Amit Sharma",
                "area_str": "3.7 Hectares",
                "area_val": 3.7,
                "village": "Pune",
                "taluka": "Haveli",
                "district": "Pune",
                "date": "10/01/2024",
                "status": "anomaly",
                "reasons": [
                    "Same Survey Number has conflicting owner and area information.",
                    "Same Survey Number (125/2) is associated with conflicting owner: 'Rajesh Patil' vs 'Amit Sharma'.",
                    "Area mismatch on Survey Number 125/2: 3.7 ha vs 2.5 ha registered under Rajesh Patil."
                ]
            }
        ]

        created_records = []
        for s in samples:
            doc_path = os.path.join(doc_dir, s["filename"])
            prep_filename = f"prep_{s['filename']}"
            prep_path = os.path.join(prep_dir, prep_filename)

            # Generate realistic document image
            create_land_document_image(
                output_path=doc_path,
                survey_no=s["survey_no"],
                owner_name=s["owner"],
                area_str=s["area_str"],
                village=s["village"],
                taluka=s["taluka"],
                district=s["district"],
                date_str=s["date"]
            )

            # Run OpenCV preprocessing
            try:
                preprocess_image(doc_path, prep_path)
            except Exception as e:
                self.stdout.write(f"Preprocess notice: {e}")

            # Run OCR
            ocr_text = run_tesseract_ocr(doc_path, prep_path)

            rec = LandRecord.objects.create(
                document=f"documents/{s['filename']}",
                preprocessed_image=f"preprocessed/{prep_filename}",
                ocr_raw_text=ocr_text,
                owner_name=s["owner"],
                survey_number=s["survey_no"],
                area=s["area_val"],
                area_unit="hectares",
                village=s["village"],
                taluka=s["taluka"],
                district=s["district"],
                record_date=s["date"],
                status=s["status"],
                anomaly_reasons=json.dumps(s["reasons"])
            )
            created_records.append(rec)
            self.stdout.write(self.style.SUCCESS(f"Created Record #{rec.id}: Survey {rec.survey_number} | {rec.owner_name} | {rec.get_status_display()}"))

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {len(created_records)} sample records."))
