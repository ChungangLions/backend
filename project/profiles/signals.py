from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import StudentProfile, StudentGroupProfile, OwnerProfile, StudentPhoto

@receiver(post_delete, sender=StudentProfile)
def delete_image_file(sender, instance, **kwargs):
    if instance.image:
        instance.image.delete(save=False)

@receiver(post_delete, sender=StudentPhoto)
def delete_image_file(sender, instance, **kwargs):
    if instance.image:
        instance.image.delete(save=False)