import json
import math
import random
from django.core.management.base import BaseCommand
from land_records.models import LandRecord


class Command(BaseCommand):
    help = "Generates realistic synthetic coordinates and multi-vertex polygon boundaries for all land records"

    def add_arguments(self, parser):
        parser.add_argument(
            '--add-extra',
            action='store_true',
            help='Also create extra synthetic parcels (available and owned) for testing'
        )

    def handle(self, *args, **options):
        self.stdout.write("Generating synthetic coordinates and polygon boundaries...")

        # Base cadastral hub: Pune / Haveli revenue district
        base_lat = 18.5204
        base_lng = 73.8567

        # Add extra synthetic parcels if requested or if total records < 8
        if options.get('add_extra') or LandRecord.objects.count() < 6:
            extra_samples = [
                {
                    'survey': '401/A',
                    'owner': '',
                    'status_own': 'available',
                    'area': 3.5,
                    'village': 'Haveli',
                    'val_status': 'consistent'
                },
                {
                    'survey': '402/B',
                    'owner': 'Government Revenue Dept (Open)',
                    'status_own': 'available',
                    'area': 5.2,
                    'village': 'Haveli',
                    'val_status': 'consistent'
                },
                {
                    'survey': '501/1',
                    'owner': 'Sunil Deshmukh',
                    'status_own': 'owned',
                    'area': 2.1,
                    'village': 'Pune',
                    'val_status': 'consistent'
                },
                {
                    'survey': '505/2',
                    'owner': 'Pooja Kulkarni',
                    'status_own': 'owned',
                    'area': 1.6,
                    'village': 'Pune',
                    'val_status': 'consistent'
                },
            ]
            for s in extra_samples:
                LandRecord.objects.get_or_create(
                    survey_number=s['survey'],
                    defaults={
                        'owner_name': s['owner'],
                        'ownership_status': s['status_own'],
                        'area': s['area'],
                        'area_unit': 'hectares',
                        'village': s['village'],
                        'taluka': 'Haveli',
                        'district': 'Pune',
                        'status': s['val_status']
                    }
                )

        records = list(LandRecord.objects.all().order_by('id'))
        count = len(records)
        self.stdout.write(f"Found {count} land records in database.")

        # Cache coordinates by survey number so conflicting claims (e.g. 125/2) overlap identically!
        survey_coord_cache = {}

        # Grid layout parameters
        cols = 4
        step_lat = 0.0075
        step_lng = 0.0090

        updated_count = 0
        for idx, rec in enumerate(records):
            s_num = (rec.survey_number or '').strip()

            if s_num in survey_coord_cache:
                # Reuse identical polygon coordinates for overlapping conflicting survey numbers!
                center_lat, center_lng, polygon = survey_coord_cache[s_num]
            else:
                # Deterministic grid placement with slight cadastral jitter
                row = idx // cols
                col = idx % cols

                # Deterministic pseudo-random offset based on record ID
                jitter_lat = ((rec.id * 17) % 10 - 5) * 0.0004
                jitter_lng = ((rec.id * 23) % 10 - 5) * 0.0004

                center_lat = round(base_lat + (row - 1) * step_lat + jitter_lat, 6)
                center_lng = round(base_lng + (col - 1.5) * step_lng + jitter_lng, 6)

                # Scale boundary polygon size according to area (hectares)
                area_factor = math.sqrt(rec.area or 2.0)
                d_lat = round(0.0016 * area_factor, 6)
                d_lng = round(0.0020 * area_factor, 6)

                # Irregular 5-point realistic cadastral boundary polygon
                p1 = [round(center_lat - d_lat * 0.9, 6), round(center_lng - d_lng * 0.85, 6)]
                p2 = [round(center_lat + d_lat * 0.8, 6), round(center_lng - d_lng * 1.05, 6)]
                p3 = [round(center_lat + d_lat * 1.05, 6), round(center_lng + d_lng * 0.65, 6)]
                p4 = [round(center_lat + d_lat * 0.3, 6), round(center_lng + d_lng * 1.15, 6)]
                p5 = [round(center_lat - d_lat * 1.1, 6), round(center_lng + d_lng * 0.75, 6)]
                polygon = [p1, p2, p3, p4, p5]

                survey_coord_cache[s_num] = (center_lat, center_lng, polygon)

            rec.latitude = center_lat
            rec.longitude = center_lng
            rec.polygon_coordinates = json.dumps(polygon)

            # Ensure effective ownership status is appropriately stored
            if not rec.ownership_status:
                owner = (rec.owner_name or '').strip().lower()
                if not owner or any(k in owner for k in ['vacant', 'government', 'unassigned', 'open', 'available']):
                    rec.ownership_status = 'available'
                else:
                    rec.ownership_status = 'owned'

            rec.save(update_fields=['latitude', 'longitude', 'polygon_coordinates', 'ownership_status'])
            updated_count += 1
            self.stdout.write(
                f" [OK] Updated Survey {rec.survey_number or rec.id}: "
                f"({center_lat}, {center_lng}) | {rec.effective_ownership_status.upper()}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully synthesized mock geospatial coordinates and boundaries for {updated_count} parcels!"
            )
        )
