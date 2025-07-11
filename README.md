# Django SwiftAPI Documentation [Still Under Development]

## Overview

**Django SwiftAPI** provides a powerful yet simple abstraction for automatically generating CRUD APIs, complete with automatic schema generation and robust file handling — currently supporting both local storage and Amazon S3, built on top of [django-ninja-extra](https://eadwincode.github.io/django-ninja-extra/). The core of this system is the use of:

- `SwiftBaseModel`: A base model with built-in support for controlling request & responses, CRUD specifications, file fields, ownership, schema customization, object validations etc all out-of-the-box.
- `SwiftBaseModelController`: A customizable controller that automates schema generations & CRUD operations. All you need to do is plug-in your `SwiftBaseModel` & it handles everything in the background. 

This documentation explains how to use these components, configure your project, and extend the system for your needs.

---

## Guide

- [Installation](#installation)
- [Database Recommendation](#database-recommendation)
- [Model Definition](#model-definition)
- [Controller Setup](#controller-setup)
- [Settings Configuration](#settings-configuration)
- [URL Configuration](#url-configuration)
- [File Handling](#file-handling)
- [Authentication & Permissions](#authentication--permissions)

---

## Installation

Before you start working, you need some familiarity on django, django-ninja & django-ninja-extra with it's modelcontrolling capabilities. 

Install it using:

`pip install django_swiftapi`

Then, add these in your INSTALLED_APPS:
```
INSTALLED_APPS = [
    ...,
    'ninja_extra',
    'django_swiftapi',
]
```
---

## Database Recommendation

- `django_swiftapi` heavily relies on the `ArrayField` for managing file-fields. So you need to use a database that supports ArrayField. Normally PostgreSQL is a good fit.

---

## Model Definition

Inherit all your models from `SwiftBaseModel` to enable automatic shema generations, CRUD and file handling. Request & response schemas are also auto-generated based on specifications of this model.

Example:

```python
from django.db import models
from django_swiftapi.modelcontrol.base_models import SwiftBaseModel
from django_swiftapi.crud_operation.files_handlers import Files_Param

class MyDocument(SwiftBaseModel):
    # You can use any django-specified fields here
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # If you're storing files:
    # Example file field (ArrayField)
    file_field = ArrayField(models.CharField(max_length=200), default=list, size=5, blank=True, null=True)
    
    ## Required configuration for file handling
    files_fields = ['file_field', ]  # Put all your file-fields names here
    files_params_list = [
        # For each file-fields, specify configurations here
        Files_Param(
            field_name="file_field",
            access="public",  # or "private"
            storage="local",  # or "amazons3"
            file_size_limit=10,  # MB
            validate_images=True,
        ),
    ]
    
    # Customize field requirements
    required_to_create = ['title']
    required_to_update = []
    
    # Exclude fields from requests/responses
    exclude_in_request = ['id', 'created', 'updated', 'created_by']  # If you override this list, make sure add these mentioned here. It will prevent showing them in the request-schema.
    exclude_in_response = []
    
    # Optional: Ownership checking
    obj_owner_check_before_save = True
    obj_fields_to_check_owner = []
```

### Model Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `exclude_in_request` | list[str] | `['id', 'created', 'updated', 'created_by']` | Specified fields here are excluded from request schemas |
| `exclude_in_response` | list[str] | `[]` | Specified fields here are excluded from response schemas |
| `required_to_create` | list[str] | `[]` | Specified fields here are treated as 'required' while creating an object of this model |
| `required_to_update` | list[str] | `[]` | Specified fields here are treated as 'required' while updating an object of this model|
| `files_fields` | list[str] | `[]` | List of file field names, these fields will be considered as file-fields by django_swiftapi|
| `files_params_list` | list[Files_Param] | `[]` | File configuration parameters for each file-field, this is required|
| `obj_owner_check_before_save` | bool | `False` | Enable ownership validation before save. enabling will tell django_swiftapi to check if the requesting user is the user that created this object |
| `obj_fields_to_check_owner` | list[str] | `[]` | A list of fields that link to other objects. Django SwiftAPI will use them to check if the user making the request created those related objects. |
| `created_by_field` | str | `'created_by'` | Field name for ownership tracking. you can modify it but default is recommended |
---

## Controller Setup

Create controllers by inheriting from `SwiftBaseModelController`:

All Configurations:

```python
from ninja_extra import api_controller, permissions
from django_swiftapi.modelcontrol.base_modelcontrollers import SwiftBaseModelController
from .models import MyDocument

@api_controller("/documents", permissions=[permissions.IsAuthenticated])
class DocumentController(SwiftBaseModelController):

    model_to_control = MyDocument

    create_enabled: bool = False
    create_path: str = 'create'
    create_info: str = 'create an item'
    create_request_schemas: list[tuple[str, str, Schema, bool]] = None
    create_response_schemas: dict[int, Schema] = None
    create_custom_permissions_list: list = []
    create_premium_check: bool = False

    retrieve_one_enabled: bool = False
    retrieve_one_path: str = 'retrieveone/{id}'
    retrieve_one_info: str = 'retrieve an item'
    retrieve_one_depth = 0
    retrieve_one_response_schemas: dict[int, Schema] = None
    retrieve_one_custom_permissions_list: list = []
    retrieve_one_obj_permission_check: bool = False
    retrieve_one_premium_check: bool = False

    filter_enabled: bool = False
    filter_path: str = 'filter'
    filter_info: str = 'filter & get the listed result'
    filter_depth = 0
    filter_request_schemas: list[tuple[str, str, Schema, bool]] = None
    filter_response_schemas: dict[int, Schema] = None
    filter_custom_permissions_list: list = []
    filter_obj_permission_check: bool = False
    filter_premium_check: bool = False

    update_enabled: bool = False
    update_path: str = '{id}/update'
    update_info: str = 'update or add files to an item'
    update_request_schemas: list[tuple[str, str, Schema, bool]] = None
    update_response_schemas: dict[int, Schema] = None
    update_custom_permissions_list: list = []
    update_obj_permission_check: bool = False
    update_premium_check: bool = False

    file_retrieve_enabled: bool = False
    file_retrieve_path: str = '{id}/file/retrieve'
    file_retrieve_info: str = 'retrieve a single file of an item'
    file_retrieve_request_schemas: list[tuple[str, str, Schema, bool]] = None
    file_retrieve_response_schemas: dict[int, Schema] = None
    file_retrieve_custom_permissions_list: list = []
    file_retrieve_obj_permission_check: bool = False
    file_retrieve_premium_check: bool = False

    files_remove_enabled: bool = False
    files_remove_path: str = '{id}/files/remove'
    files_remove_info: str = 'remove files of an item', 
    files_remove_request_schemas: list[tuple[str, str, Schema, bool]] = None
    files_remove_response_schemas: dict[int, Schema] = None
    files_remove_custom_permissions_list: list = []
    files_remove_obj_permission_check: bool = False
    files_remove_premium_check: bool = False

    delete_enabled: bool = False
    delete_path: str = '{id}/delete'
    delete_info: str = 'delete an item with all its files'
    delete_response_schemas: dict[int, Schema] = None
    delete_custom_permissions_list: list = []
    delete_obj_permission_check: bool = False
    delete_premium_check: bool = False
```

### Controller Options

#### CRUD Operations

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `create_enabled` | bool | `False` | Enable create endpoint |
| `retrieve_one_enabled` | bool | `False` | Enable retrieve endpoint |
| `filter_enabled` | bool | `False` | Enable filter/search endpoint |
| `update_enabled` | bool | `False` | Enable update endpoint |
| `delete_enabled` | bool | `False` | Enable delete endpoint |

#### File Operations

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `file_retrieve_enabled` | bool | `False` | Enable file retrieval endpoint |
| `files_remove_enabled` | bool | `False` | Enable file removal endpoint |

#### Permission Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `*_custom_permissions_list` | list | `[]` | Custom permissions for specific operation |
| `*_obj_permission_check` | bool | `False` | Check object ownership for operation |

#### Path Customization (You can leave it to the default)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `create_path` | str | `'create'` | Custom path for create endpoint |
| `retrieve_one_path` | str | `'retrieveone/{id}'` | Custom path for retrieve endpoint |
| `filter_path` | str | `'filter'` | Custom path for filter endpoint |
| `update_path` | str | `'{id}/update'` | Custom path for update endpoint |
| `delete_path` | str | `'{id}/delete'` | Custom path for delete endpoint |
| `file_retrieve_path` | str | `'{id}/file/retrieve'` | Custom path for file retrieve |
| `files_remove_path` | str | `'{id}/files/remove'` | Custom path for file removal |

You can also customize their `info` and `schemas`. just set the variables properly.

---

## URL Configuration

Configure your URLs to include the API endpoints ([Reference](#https://eadwincode.github.io/django-ninja-extra/)):

```python
# urls.py
from django.contrib import admin
from django.urls import path, include
from ninja_extra import NinjaExtraAPI
from your_app.controllers import DocumentController

api = NinjaExtraAPI()
api.register_controllers(DocumentController)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## File Handling

### File Configuration

Configure file handling using `Files_Param`:

```python
from crud_operation.files_handlers import Files_Param

files_params_list = [
    Files_Param(
        field_name="name_of_your_field",    # Field name in model
        access="public",                    # "public" or "private"
        storage="local",                    # "local" or "amazons3"
        file_size_limit=10,                 # Size limit in MB
        validate_images=True,               # Validate image files
    ),
    Files_Param(
        field_name="name_of_your_field",
        access="private",
        storage="amazons3",
        file_size_limit=20,
        validate_images=False,
    ),
]
```

### File Operations

The system automatically provides these file operations:

- **Upload**: Files are uploaded during create/update operations
- **Retrieve**: Download files via `/file/retrieve` endpoint
- **Remove**: Delete specific files via `/files/remove` endpoint
- **Storage**: Automatic handling of local and S3 storage

### File Access Control

- **Public files**: Accessible without authentication
- **Private files**: Require authentication and ownership verification

---

## Authentication & Permissions
`django_swiftapi` is highly compatible with [django-allauth](#https://docs.allauth.org/en/latest/). So, if you're using django-allauth, you can validate authentications directly in your modelcontrollers.

### Using Built-in Authentication Classes

```python
from django_swiftapi.modelcontrol.authenticators import (
    djangoallauth_UserAuthentication,
    base_UserAuthentication
)

# Using allauth authentication
@api_controller("/api", permissions=[djangoallauth_UserAuthentication()])
class MyController(SwiftBaseModelController):
    pass
```

### Customizing Authentication Class

If you're using any other user authentication system, you need to define your own authentication class overriding just one function:
```
# Create custom authentication
class CustomAuthentication(base_UserAuthentication):
    def has_permission(self, request, view):
        # Your custom logic for verifying if the user is authenticated
        # return the user object if authenticated else None
```
then use it like this:
```
@api_controller("/api", permissions=[CustomAuthentication()])
class MyController(SwiftBaseModelController):
    pass
```

### Permission Levels

1. **Controller Level**: Applied to all endpoints in the controller
2. **Operation Level**: Specific permissions per CRUD operation
3. **Object Level**: Ownership-based permissions

### Ownership Checking

Enable object-level permissions:

```python
class DocumentController(SwiftBaseModelController):
    retrieve_one_obj_permission_check = True  # Only owner can retrieve
    update_obj_permission_check = True        # Only owner can update
    delete_obj_permission_check = True        # Only owner can delete
```

---

### Filtering and Search

The filter endpoint supports:

- Field-based filtering
- Search functionality via URL parameters
- Pagination [Can be set according to django-ninja [specs](#https://django-ninja.dev/guides/response/pagination/)]
- Custom filter expressions

Example filter request:
```
POST /api/documents/filter
{
    "title": "My Document",
    "created__gte": "2024-01-01"
}
```

---


