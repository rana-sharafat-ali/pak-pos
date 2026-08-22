import json
from django.db import models

class EmailQueue(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('failed', 'Failed'),
        ('sent', 'Sent'),
    )
    
    subject = models.CharField(max_length=255)
    text_content = models.TextField()
    html_content = models.TextField(blank=True, null=True)
    to_emails = models.TextField(help_text="JSON encoded list of emails")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True, null=True)
    
    def set_emails(self, email_list):
        self.to_emails = json.dumps(email_list)
        

    def get_emails(self):
        try:
            return json.loads(self.to_emails)
        except:
            return []

    def __str__(self):
        return f"{self.subject} ({self.status})"

class SystemSetting(models.Model):
    """
    Singleton pattern model for application settings.
    Only one row (id=1) will ever exist in this table.
    """
    # Branding
    app_name = models.CharField(max_length=100, default='PakPOS')
    app_subtitle = models.CharField(max_length=200, default='Professional Point of Sale')
    app_currency = models.CharField(max_length=20, default='PKR')
    app_footer_text = models.CharField(max_length=200, default='Powered by PakPOS')
    app_primary_color = models.CharField(max_length=20, default='#2563eb')
    
    # Operation Mode
    pos_operation_mode = models.CharField(max_length=50, default='restaurant', choices=[('retail', 'Retail'), ('restaurant', 'Restaurant')])
    time_zone = models.CharField(max_length=100, default='Asia/Karachi')
    
    # Defaults
    pos_default_tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    pos_default_service_charge_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    pos_default_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    pos_auto_apply_discount = models.BooleanField(default=False)
    pos_default_delivery_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    
    # Shift Times
    pos_shift_start_hour = models.IntegerField(default=0)
    pos_shift_end_hour = models.IntegerField(default=23)
    
    # Pagination & Session
    products_per_page = models.IntegerField(default=50)
    session_cookie_age_days = models.IntegerField(default=30)
    
    # Owner Emails
    owner_email_1 = models.EmailField(blank=True, null=True)
    owner_email_2 = models.EmailField(blank=True, null=True)
    owner_email_3 = models.EmailField(blank=True, null=True)
    email_enabled = models.BooleanField(default=True, help_text="Global switch to enable/disable background email sending")

    # Google Drive Automated Cloud Backup
    gdrive_backup_enabled = models.BooleanField(default=True, help_text="Enable/disable Google Drive cloud backup")
    gdrive_remote_active = models.BooleanField(default=True, help_text="Controlled via Google Sheets Actions tab 'backup_active'")
    gdrive_webhook_url = models.CharField(max_length=500, blank=True, null=True, help_text="Google Apps Script Webhook URL")
    gdrive_folder_id_or_link = models.CharField(max_length=500, blank=True, null=True, help_text="Google Drive Folder Link or Folder ID")
    gdrive_backup_time = models.CharField(max_length=10, default="23:00", help_text="Daily backup schedule time (HH:MM in 24-hour format)")
    gdrive_max_files = models.IntegerField(default=3, help_text="Number of latest backup files to retain on Google Drive")
    gdrive_last_upload_time = models.DateTimeField(null=True, blank=True)
    gdrive_last_upload_status = models.CharField(max_length=255, blank=True, null=True)
    gdrive_last_file_url = models.URLField(max_length=500, blank=True, null=True)
    
    # Sync metadata
    is_synced = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"

    def save(self, *args, **kwargs):
        # Enforce Singleton pattern: always save to id=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """
        Fetch the singleton instance. If it doesn't exist, create it with defaults.
        """
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Global System Settings"


class PaymentAlert(models.Model):
    """
    Singleton model for Payment Alert, Due Reminder & Navbar Notification.
    Controlled dynamically via Google Sheets 'Actions' tab.
    """
    is_popup_active = models.BooleanField(default=False, help_text="Enable or disable the recurring popup modal")
    is_navbar_active = models.BooleanField(default=False, help_text="Enable or disable the top navbar badge")
    interval_minutes = models.IntegerField(default=15, help_text="Popup re-occurrence interval in minutes after dismissal")
    pending_month = models.CharField(max_length=100, default='Current Month', blank=True, help_text="Month or period for which payment is due")
    pending_amount = models.CharField(max_length=100, default='0', blank=True, help_text="Amount due (e.g. Rs. 15,000)")
    account_info = models.TextField(blank=True, default='', help_text="Bank details, Account Title, Account No, Raast ID, IBAN")
    alert_title = models.CharField(max_length=200, default='Software Subscription Payment Due', blank=True)
    alert_message = models.TextField(blank=True, default='Your monthly POS software maintenance/subscription fee is pending. Please transfer the payment to keep all system services running without disruption.')
    due_date = models.CharField(max_length=100, blank=True, default='', help_text="Due date (e.g. 25-Aug-2026 or Immediate)")
    contact_info = models.CharField(max_length=200, blank=True, default='', help_text="Support helpline / WhatsApp")
    
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payment Alert"
        verbose_name_plural = "Payment Alerts"

    @property
    def is_active(self):
        return self.is_popup_active or self.is_navbar_active

    def save(self, *args, **kwargs):
        # Enforce Singleton pattern: always save to id=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """
        Fetch the singleton instance. If it doesn't exist, create it with defaults.
        """
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Payment Alert [Popup: {self.is_popup_active}, Navbar: {self.is_navbar_active}] - Month: {self.pending_month} | Interval: {self.interval_minutes}m"

