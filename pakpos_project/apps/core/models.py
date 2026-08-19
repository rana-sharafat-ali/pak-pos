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
