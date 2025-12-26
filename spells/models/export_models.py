import json

from django.apps import apps

models = []
for model in apps.get_models():
    fields = []
    for field in model._meta.get_fields():
        field_info = {
            "name": field.name,
            "type": field.get_internal_type(),
            "related_model": field.related_model.__name__
            if hasattr(field, "related_model") and field.related_model
            else None,
        }
        fields.append(field_info)

    models.append({"name": model.__name__, "fields": fields})

with open("models_export.json", "w") as f:
    json.dump(models, f, indent=2)
