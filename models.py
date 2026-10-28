from django.db import models
import json

class LandRecord(models.Model):
    STATUS_CHOICES = [
        ('consistent', 'Consistent'),
        ('warning', 'Requires Verification'),
        ('anomaly', 'Anomaly Detected'),
    ]

    # Ownership Status Choices
    OWNERSHIP_CHOICES = [
        ('available', 'Empty/Available'),
        ('owned', 'Bought/Owned'),
    ]

    # File uploads
    document = models.FileField(upload_to='documents/', null=True, blank=True)
    preprocessed_image = models.ImageField(upload_to='preprocessed/', null=True, blank=True)
    
    # OCR output
    ocr_raw_text = models.TextField(blank=True, default='')
    
    # Extracted structured fields
    owner_name = models.CharField(max_length=255, blank=True, default='')
    survey_number = models.CharField(max_length=100, blank=True, default='', db_index=True)
    area = models.FloatField(null=True, blank=True, help_text="Area in hectares or specified unit")
    area_unit = models.CharField(max_length=50, default='hectares')
    village = models.CharField(max_length=150, blank=True, default='')
    taluka = models.CharField(max_length=150, blank=True, default='')
    district = models.CharField(max_length=150, blank=True, default='')
    record_date = models.CharField(max_length=100, blank=True, default='')

    # Geospatial Coordinates (Leaflet.js integration)
    latitude = models.FloatField(null=True, blank=True, help_text="Latitude coordinate (e.g., 18.5204)")
    longitude = models.FloatField(null=True, blank=True, help_text="Longitude coordinate (e.g., 73.8567)")
    polygon_coordinates = models.TextField(blank=True, default='', help_text="JSON list of [lat, lng] coordinate pairs for parcel polygon")

    # Ownership status
    ownership_status = models.CharField(
        max_length=20,
        choices=OWNERSHIP_CHOICES,
        default='owned',
        blank=True,
        help_text="Status: Empty/Available or Bought/Owned"
    )

    # Validation and Anomaly Detection
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='warning')
    anomaly_reasons = models.TextField(blank=True, default='', help_text="Newline or JSON separated list of anomaly/verification reasons")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Survey {self.survey_number or 'N/A'} - {self.owner_name or 'Unknown'} ({self.get_status_display()})"

    @property
    def anomaly_list(self):
        """Return list of anomaly strings."""
        if not self.anomaly_reasons:
            return []
        try:
            data = json.loads(self.anomaly_reasons)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return [line.strip() for line in self.anomaly_reasons.split('\n') if line.strip()]

    @property
    def status_label(self):
        if self.status == 'consistent':
            return 'Consistent'
        elif self.status == 'warning':
            return 'Requires Verification'
        elif self.status == 'anomaly':
            return 'Anomaly Detected'
        return self.status

    @property
    def status_badge_class(self):
        if self.status == 'consistent':
            return 'badge-consistent'
        elif self.status == 'warning':
            return 'badge-warning'
        elif self.status == 'anomaly':
            return 'badge-anomaly'
        return 'badge-secondary'

    @property
    def status_icon(self):
        if self.status == 'consistent':
            return '🟢'
        elif self.status == 'warning':
            return '🟡'
        elif self.status == 'anomaly':
            return '🔴'
        return '⚪'

    @property
    def effective_ownership_status(self):
        """Derive status: Empty/Available or Bought/Owned."""
        if self.ownership_status:
            return self.ownership_status
        owner = (self.owner_name or '').strip().lower()
        if not owner or owner in ['none', 'n/a', 'available', 'empty', 'unassigned', 'government', 'govt']:
            return 'available'
        return 'owned'

    @property
    def ownership_label(self):
        return 'Empty/Available' if self.effective_ownership_status == 'available' else 'Bought/Owned'

    @property
    def map_color(self):
        """Green for Empty/Available, Red for Bought/Owned"""
        return '#10b981' if self.effective_ownership_status == 'available' else '#ef4444'

