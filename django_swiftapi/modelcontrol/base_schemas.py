from typing import Any, Literal, Optional, List, Type
from pydantic import create_model
from pydantic.fields import FieldInfo
from django.db import models
from django.db.models import Model, ForeignKey, OneToOneField, ManyToManyField, Q
from django.core.exceptions import ImproperlyConfigured
from ninja import Schema, ModelSchema, FilterSchema, filter_schema
from ninja.orm import create_schema
from ninja.files import UploadedFile



class MessageResponseSchema(Schema):
    message: str

class InfoResponseSchema(Schema):
    info: dict

def create_custom_schema(
        model:Model, 
        schema_type: Literal['request', 'response'], 
        action: Literal["create", "retrieve", "filter", "update", "delete"], 
        depth=0, 
        optional_fields='__all__'
    ):
    if schema_type == 'request':
        exclude = model.exclude_in_request + model.files_fields
        exclude = list(set(exclude)) or []
    elif schema_type == 'response':
        exclude = model.exclude_in_response or []

    general_schema = create_schema(model=model, exclude=exclude, optional_fields=optional_fields)

    schema_fields = {}
    for field in model._meta.fields:
        field_name = field.name
        if field_name in exclude:
            continue
        if field.choices:
            choices = [choice[0] for choice in field.choices]
            schema_fields[field_name] = (Literal[tuple(choices)], None)
        if isinstance(field, (ForeignKey, OneToOneField)) and depth>0:
            field_model = field.related_model
            schema_fields[field_name] = (create_custom_schema(model=field_model, schema_type=schema_type, action=action, depth=depth-1,), None)
        
    schema = create_model(
        model.__name__ + action + schema_type + "Schema",
        **schema_fields,
        __base__=general_schema,
    )
    return schema

def schema_generator(
        model: Model, 
        schema_type: Literal['request', 'response'],
        action: Literal["create", "retrieve", "filter", "update", "delete"], 
        files_fields_only = False, # if true, schema will only contain files fields. this will only effect `request schemas`
        custom_depth: int = None # this defines the depth of the relational fields of the  response schema. this only effects `response` schemas
    ):

    if schema_type=='request':
        """
        if schema_type='request', then it returns a list of tuples of the schema along with their configs. all schemas are `required=False` by default
        """
        schemas = []
        depth = 0
        
        # all_fields = model._meta.get_fields() # set(model._meta.get_fields())

        if not files_fields_only:
            schemas.append(("request_body", "request_body_schema", create_custom_schema(model=model, schema_type=schema_type, action=action), False))

        files_fields = model.files_fields
        if files_fields:
            if action=="create" or action=="update":
                for files_field in files_fields:
                    schemas.append((f"{files_field}", f"{files_field}_schema", List[UploadedFile], False))
            if action=="retrieve" or action=="delete":
                for files_field in files_fields:
                    schemas.append((f"{files_field}", f"{files_field}_schema", List[str], False))
                if len(files_fields)==1 and files_fields_only:
                    schemas.append((f"ignore_this", f"ignore_schema", List[str], False))

    elif schema_type=='response':
        """
        if schema_type='response', then it returns a dict with all the schemas along with their status codes
        """
        schemas = {}
        depth = custom_depth or 0
        # exclude = model.exclude_in_response
        if action == "filter":
            # schemas[200] = List[create_schema(model=model, depth=depth, exclude=exclude)]
            schemas[200] = List[create_custom_schema(model=model, schema_type=schema_type, depth=depth, action=action)]
        else:
            # schemas[200] = create_schema(model=model, depth=depth, exclude=exclude)
            schemas[200] = create_custom_schema(model=model, schema_type=schema_type, depth=depth, action=action)
    
    return schemas

class CustomFilterSchema(FilterSchema):

    """
    Curently `FilterSchema.get_filter_expression()` throws error if a value of a ManyToMany field is provided. I did a Pull Request to the django-ninja repo with this fix a couple days ago which haven't been merged yet. So, I extended the class with this fix. 
    """

    def _resolve_field_expression(
        self, field_name: str, field_value: Any, field: FieldInfo
    ) -> Q:
        func = getattr(self, f"filter_{field_name}", None)
        if callable(func):
            return func(field_value)  # type: ignore[no-any-return]

        field_extra = field.json_schema_extra or {}

        q_expression = field_extra.get("q", None)  # type: ignore
        if not q_expression:
            if isinstance(field_value, list):
                return Q(**{f"{field_name}__in": field_value})
            return Q(**{f"{field_name}": field_value})
        elif isinstance(q_expression, str):
            if q_expression.startswith("__"):
                q_expression = f"{field_name}{q_expression}"
            return Q(**{q_expression: field_value})
        elif isinstance(q_expression, list):
            expression_connector = field_extra.get(  # type: ignore
                "expression_connector", filter_schema.DEFAULT_FIELD_LEVEL_EXPRESSION_CONNECTOR
            )
            q = Q()
            for q_expression_part in q_expression:
                q_expression_part = str(q_expression_part)
                if q_expression_part.startswith("__"):
                    q_expression_part = f"{field_name}{q_expression_part}"
                q = q._combine(  # type: ignore
                    Q(**{q_expression_part: field_value}),
                    expression_connector,
                )
            return q
        else:
            raise ImproperlyConfigured(
                f"Field {field_name} of {self.__class__.__name__} defines an invalid value under 'q' kwarg.\n"
                f"Define a 'q' kwarg as a string or a list of strings, each string corresponding to a database lookup you wish to filter against:\n"
                f"  {field_name}: {field.annotation} = Field(..., q='<here>')\n"
                f"or\n"
                f"  {field_name}: {field.annotation} = Field(..., q=['lookup1', 'lookup2', ...])\n"
                f"You can omit the field name and make it implicit by starting the lookup directly by '__'."
                f"Alternatively, you can implement {self.__class__.__name__}.filter_{field_name} that must return a Q expression for that field"
            )

def filterschema_generator(model: Type[Model]) -> Type[Schema]:
    # Get the app_label and model_name
    app_label = model._meta.app_label
    model_name = model._meta.model_name

    # Get the list of fields to exclude
    exclude_fields = getattr(model, 'exclude_in_request', []) + model.files_fields

    # Prepare the dynamic attributes for the FilterSchema
    schema_fields = {}
    
    # Loop through all model fields
    for field in model._meta.get_fields():
        field_name = field.name
        
        # Skip excluded fields
        if field_name in exclude_fields:
            continue

        # Set the correct type annotation for each field
        if isinstance(field, ForeignKey) or isinstance(field, OneToOneField):
            # ForeignKey and OneToOneField should be treated as integer IDs
            field_type = Optional[int]
        elif isinstance(field, ManyToManyField):
            # ManyToManyField should be treated as a list of integer IDs
            field_type = Optional[List[int]]
        elif isinstance(field, (models.CharField, models.TextField)):
            field_type = Optional[str]
        elif isinstance(field, models.IntegerField):
            field_type = Optional[int]
        elif isinstance(field, models.BooleanField):
            field_type = Optional[bool]
        elif isinstance(field, models.FloatField):
            field_type = Optional[float]
        # Add more field types as needed
        else:
            field_type = Optional[str]  # Defaulting to string if unhandled
        
        # Add the field to the schema
        schema_fields[field_name] = (field_type, None)

    # Generate the schema name dynamically
    schema_name = f'{app_label}_{model_name}FilterRequestSchema'

    # Use pydantic's `create_model` to create a dynamic schema class
    filter_schema = create_model(schema_name, **schema_fields, __base__=CustomFilterSchema)

    return [("filters", "request_body_schema", filter_schema, False)]
    
