from django.contrib import admin
from .models import (
    Category,
    Subject,
    SyllabusVersion,
    Topic,
    Subtopic,
    Question,
)

admin.site.register(Category)
admin.site.register(Subject)
admin.site.register(SyllabusVersion)
admin.site.register(Topic)
admin.site.register(Subtopic)
admin.site.register(Question)