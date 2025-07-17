# Django SwiftAPI Documentation

## Overview

**Django SwiftAPI**, a fully async API framework, provides a powerful yet simple abstraction for automatically generating CRUD APIs, schema generation and robust file handling, built on top of [django-ninja-extra](https://eadwincode.github.io/django-ninja-extra/). The core of this system is the use of:

- `SwiftBaseModel`: A base model with built-in support for controlling request & responses, CRUD specifications, file fields, ownership, schema customization, object validations etc all out-of-the-box.
- `SwiftBaseModelController`: A customizable controller that automates schema generations & CRUD operations. All you need to do is plug-in your `SwiftBaseModel` & it handles everything in the background. 

This documentation explains how to use these components, configure your project, and extend the system for your needs.

---

## Guide

- [Installation](#installation)
- [Database Recommendation](#database-recommendation)
- [Usage](#usage)
- [Model Definition](#model-definition)
- [Model-Controller Setup](#model-controller-setup)
- [URL Configuration](#url-configuration)
- [File Handling](#file-handling)
- [Authentication & Permissions](#authentication--permissions)

---

## Installation

Install it using:
```bash
pip install django-swiftapi
```

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

- `django-swiftapi` heavily relies on the `ArrayField` for managing file-fields. So you need to use a database that supports ArrayField. Normally, PostgreSQL is a good fit.

---

## Usage Guide for Django SwiftAPI

Welcome to the **Django-SwiftAPI** usage tutorial. This guide will walk you through setting up a fully functional async API server with minimal effort — from starting your project to building secure, filterable, paginated API endpoints backed by user authentication.

> **Django-SwiftAPI** is designed for rapid API development. With just a few lines of code, you get models, controllers, CRUD, filtering, search, pagination, file-handling and authentication — all built on top of Django Ninja and Django Ninja Extra

---

### Project Setup

#### Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: source venv/Scripts/activate
```

#### Install django-swiftapi

```bash
pip install django-swiftapi
```

#### Start your project and an app like a regular django project

```bash
django-admin startproject myproject
cd myproject
python manage.py startapp api
```

#### Add required apps in `settings.py`

```python
INSTALLED_APPS = [
    ...
    "ninja_extra",
    "django_swiftapi",
    "api",  # your app
]
```

---

### Create Your Models

#### Extend `SwiftBaseModel` instead of `models.Model`

```python
# api/models.py
from django.db import models
from django_swiftapi.modelcontrol.models import SwiftBaseModel

class Product(SwiftBaseModel):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=50)
```

Run migrations:

```bash
python manage.py makemigrations
python manage.py migrate
```

---

### Set up a Model-Controller

> Full functional CRUD APIs with automatic files-handling support

#### Create `api/modelcontrollers.py`

```python
# api/modelcontrollers.py
from ninja_extra import api_controller
from django_swiftapi.modelcontrol.modelcontrollers import SwiftBaseModelController
from .models import Product

@api_controller("/product",)
class ProductController(SwiftBaseModelController):
    model_to_control = Product

    create_enabled = True
    retrieve_one_enabled = True
    filter_enabled = True
    update_enabled = True
    delete_enabled = True
```

---

#### Connect the model-controller to your project's root `urls.py`

```python
from django.contrib import admin
from django.urls import path, include
from ninja_extra import NinjaExtraAPI
from api.modelcontrollers import ProductController

# Register the controller with your API
api_routes = NinjaExtraAPI(
    title="myproject",
    version="development",
    description="my cool project!",
)
api_routes.register_controllers(ProductController,)

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", api_routes.urls),  # this is where all your endpoints live
]
```

✅ That's literally it! Now, `Product` is available at `/api/product` with full CRUD support! 

First, let's start our server with [uvicorn](https://pypi.org/project/uvicorn/):
```
pip install uvicorn
uvicorn myproject.asgi:application --reload
```
Now, go to `http://127.0.0.1:8000/api/docs` to find all the routes with request-response examples.

---

### Auto-Generated Documentation

Thanks to ninja & ninja-extra, your project's full api documentation is accessible at `/api/docs`.

Example url: `http://127.0.0.1:8000/api/docs`

---

### Filtering and Search (Out of the Box!)

You don't need to implement anything. Django-SwiftAPI automatically enables all filtering functionalities in the `/filter` route using Django Ninja’s features.

Try accessing:
```
curl -X POST http://127.0.0.1:8000/api/product/filter \
     -H "Content-Type: application/json" \
     -d '{}'
```
This is basically a `POST` request to the route `http://127.0.0.1:8000/api/product/filter` with an empty json body. This will return all product instances with a default pagination of 100 items (you can change it [here](#pagination)). You can easily filter items if a body is provided:
```
curl -X POST http://127.0.0.1:8000/api/product/filter \
     -H "Content-Type: application/json" \
     -d '{"name": "earbuds", "price": "10.0"}'
```
This will return all the results containing matches either the "name" or the "price" or both.

[Reference](https://django-ninja.dev/guides/input/filtering/)

---

### Pagination

When you use any `/filter` endpoint in Django-SwiftAPI, results are paginated by default. All the following functionalities are provided by [django-ninja](https://django-ninja.dev/guides/response/pagination/)

#### Default Behavior

By default, 100 items per page are returned in each response. This is controlled by Django Ninja’s default setting.

You can change the default limit globally for your project by adding this to your `settings.py`:

```python
NINJA_PAGINATION_PER_PAGE = 50  # or any number you prefer
```

Now, every paginated endpoint will return 50 items per page unless manually overridden.

#### Customize Per Request

If you want to control pagination manually for any request, you can add query parameters:

- `/api/product/?limit=10&offset=0`
- `/api/product/?page=2`

##### What do these mean?

| Parameter | Description |
|----------|-------------|
| `limit`  | How many items you want per page (e.g., `10`) |
| `offset` | How many items to skip before starting to return results. For example, `offset=0` starts from the beginning, `offset=10` skips the first 10. |
| `page`   | Shortcut to jump to a specific page. If `limit=10`, then `page=2` means `offset=10` (i.e., skip the first 10 items). |

You can use either `limit` + `offset` **or** just `page` — whichever feels easier.

#### Example

```http
POST /api/product/?limit=5&offset=10
```

This will return 5 products, starting from the 11th product.

```http
POST /api/product/?page=3
```

Assuming default page size is 100, this will return items from 201 to 300.

---

### Authentication

If you're using [django-allauth](https://docs.allauth.org/en/latest/), `django_swiftapi` has a built-in authentication class for it. You can use it directly in your modelcontrollers:
```python
from ninja_extra import api_controller
from django_swiftapi.modelcontrol.modelcontrollers import SwiftBaseModelController
from django_swiftapi.modelcontrol.authenticators.django_allauth import djangoallauth_userauthentication

# Using allauth authentication
@api_controller("/product", permissions=[djangoallauth_userauthentication()])
class ProductController(SwiftBaseModelController):
    # your codes
```
This will enable authentication for all the routes in that modelcontroller. 

If you prefer to allow certain routes without authentication, you can do it simply:

```python
from ninja_extra import api_controller, permissions
from django_swiftapi.modelcontrol.modelcontrollers import SwiftBaseModelController
from django_swiftapi.modelcontrol.authenticators.django_allauth import djangoallauth_userauthentication

@api_controller("/product", permissions=[djangoallauth_userauthentication()])
class ProductController(SwiftBaseModelController):

    create_enabled= True
    create_custom_permissions_list = [permissions.AllowAny]
```
Now, the `/create` route can be accessed by anyone. If you wanna use a custom authentication class, follow this [guideline](https://github.com/DeepDiverGuy/django-swiftapi?tab=readme-ov-file#authentication--permissions).

---
### Extending API Routes

If the built-in functionalities don't meet your needs and you want your own routes & custom functionalities, simply define a method inside the model-controller class and put your own logics. Follow the official documentation from [django-ninja-extra](https://eadwincode.github.io/django-ninja-extra/api_controller/api_controller_route/).

---

### Admin Panel

One of the best features of [Django](https://www.djangoproject.com/) is that it provides a robust and customizable Admin Panel. You can register the models in `admin.py` as usual:
```python
from django.contrib import admin
from .models import Product

admin.site.register(Product)
```

To access the admin panel, first you need to create a superuser from your terminal:
```
python manage.py createsuperuser
```

The admin panel is accessible at `http://127.0.0.1:8000/admin/`

---

### Final Words

Django-SwiftAPI removes boilerplate and makes you productive in minutes. Compared to Django Ninja or FastAPI, you write:
- ✅ No manual schema or serializers
- ✅ No explicit views
- ✅ No filters setup
- ✅ No pagination configuration
- ✅ Everything is automatic via configuration and base classes

Happy Hacking 🚀


---


## Model Definition

### SwiftBaseModel

`SwiftBaseModel` is an abstract Django model that provides powerful hooks and configurations for automated CRUD operations, user ownership enforcement, and file upload handling when used with the `crud_handler` and `SwiftBaseModelController` from `django-swiftapi`.


### Key Features

- Auto-included `created`, `updated`, and `created_by` fields
- Ownership-based object access control
- Field-level validation before save/update
- Built-in file handling for `ArrayField`-based file storage
- Built-in integration with both local and S3-based file systems


### Full Model Example Using `SwiftBaseModel`

```python
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django_swiftapi.modelcontrol.models import SwiftBaseModel
from django_swiftapi.crud_operation.file_operations.storage_operations import local_storage
from django_swiftapi.crud_operation.file_operations.files_handlers import Files_Param
from django_swiftapi.crud_operation.file_operations.files_validators import validate_images, validate_file_sizes

class Product(SwiftBaseModel):
    name = models.CharField(max_length=100)
    images = ArrayField(models.CharField(max_length=200), default=list, blank=True, null=True)

    files_fields = ["images"]
    files_params_list = [
        FilesParam(
            field_name="images",
            access="public",
            storage=local_storage,
            validator_funcs={
                file_sizes_valid: {"limit": 5},
                images_valid: {},
            }
        )
    ]
```


### Model Fields

| Field              | Type                 | Description                                                   |
|-------------------|----------------------|---------------------------------------------------------------|
| `created`          | `DateTimeField`      | Auto timestamp when instance is created                       |
| `updated`          | `DateTimeField`      | Auto timestamp on every update                                |
| `created_by`       | `ForeignKey(User)`   | Automatically assigned user who created the object            |
| `created_by_field` | `str` (default: `'created_by'`) | Custom field to use for ownership checking      |


### Configuration Attributes

These are **class-level attributes**, not DB fields.

| Attribute                     | Type         | Description                                                                 |
|-------------------------------|--------------|-----------------------------------------------------------------------------|
| `required_to_create`          | `list[str]`  | List of field names required during object creation                         |
| `required_to_update`          | `list[str]`  | List of field names required during update                                  |
| `exclude_in_request`          | `list[str]`  | Fields to exclude while generating request schemas                          |
| `exclude_in_response`         | `list[str]`  | Fields to exclude from response schemas                                     |
| `obj_owner_check_before_save` | `bool`       | If `True`, ownership will be verified before saving                         |
| `files_fields`                | `list[str]`  | Names of file fields (typically `ArrayField`s)                              |
| `files_params_list`           | `list[FilesParam]` | Full configuration for file handling per field                        |


### File Handling Example

To manage file uploads, downloads, deletion etc (via `ArrayField`), follow this approach:

```python
from django.contrib.postgres.fields import ArrayField
from django_swiftapi.crud_operation.file_operations.storage_operations import local_storage
from django_swiftapi.crud_operation.file_operations.files_handlers import Files_Param
from django_swiftapi.crud_operation.file_operations.files_validators import validate_images, validate_file_sizes

# Define file field in your model:
images = ArrayField(
    models.CharField(max_length=200), 
    default=list, 
    size=5, 
    blank=True, 
    null=True
)

# Register it as a file field:
files_fields = ["images"]

# Provide full configuration for how files should be handled:
files_params_list = [
    FilesParam(
        field_name="images",
        access="public",
        storage=local_storage,
        validator_funcs={
            file_sizes_valid: {"limit": 10},  # limit in MB
            images_valid: {}
        }
    ),
]
```


### Ownership Enforcement

By default, `created_by` is used to check whether the requesting user has access to modify or delete the object.

To enable this behavior, set:

```python
obj_owner_check_before_save = True
```

If you use a different field for ownership, specify it with:

```python
created_by_field = "your_owner_field_name"
```


### Summary of Key Attributes

| Attribute               | Type           | Description |
|-------------------------|----------------|-------------|
| `required_to_create`    | `list[str]`    | Fields required when creating an object (only applies during `crud_handler` operations) |
| `required_to_update`    | `list[str]`    | Fields required when updating an object (only applies during `crud_handler` operations) |
| `exclude_in_request`    | `list[str]`    | Fields to exclude from request schema generation |
| `exclude_in_response`   | `list[str]`    | Fields to exclude from response schema generation |
| `files_fields`          | `list[str]`    | List of fields representing file arrays (usually Django `ArrayField`) |
| `files_params_list`     | `list[FilesParam]` | List of `FilesParam` configurations for each file field |
| `obj_owner_check_before_save` | `bool`  | Whether to enforce ownership validation before saving an object |
| `created_by_field`      | `str`          | Name of the field used for ownership validation (default `"created_by"`) |


This documentation outlines how to utilize the `SwiftBaseModel` to build models that seamlessly integrate with the CRUD operations and file handling mechanisms provided by django-swiftapi.

For more details on file validations and storage options, refer to the respective modules.

---

## Model-Controller Setup

Create modelcontrollers by inheriting from `SwiftBaseModelController`:

### Full Configurations Example:

```python
from ninja_extra import api_controller
from django_swiftapi.modelcontrol.modelcontrollers import SwiftBaseModelController
from .models import MyDocument

@api_controller("/documents",)
class DocumentController(SwiftBaseModelController):

    model_to_control = MyDocument

    # These are default values
    create_enabled: bool = False
    create_path: str = 'create'
    create_info: str = 'create an item'
    create_request_schemas: list[tuple[str, str, Schema, bool]] = None
    create_response_schemas: dict[int, Schema] = None
    create_custom_permissions_list: list = []

    retrieve_one_enabled: bool = False
    retrieve_one_path: str = 'retrieveone/{id}'
    retrieve_one_info: str = 'retrieve an item'
    retrieve_one_depth = 0
    retrieve_one_response_schemas: dict[int, Schema] = None
    retrieve_one_custom_permissions_list: list = []
    retrieve_one_obj_permission_check: bool = False

    filter_enabled: bool = False
    filter_path: str = 'filter'
    filter_info: str = 'filter & get the listed result'
    filter_depth = 0
    filter_request_schemas: list[tuple[str, str, Schema, bool]] = None
    filter_response_schemas: dict[int, Schema] = None
    filter_custom_permissions_list: list = []
    filter_obj_permission_check: bool = False

    update_enabled: bool = False
    update_path: str = '{id}/update'
    update_info: str = 'update or add files to an item'
    update_request_schemas: list[tuple[str, str, Schema, bool]] = None
    update_response_schemas: dict[int, Schema] = None
    update_custom_permissions_list: list = []
    update_obj_permission_check: bool = False

    file_retrieve_enabled: bool = False
    file_retrieve_path: str = '{id}/file/retrieve'
    file_retrieve_info: str = 'retrieve a single file of an item'
    file_retrieve_request_schemas: list[tuple[str, str, Schema, bool]] = None
    file_retrieve_response_schemas: dict[int, Schema] = None
    file_retrieve_custom_permissions_list: list = []
    file_retrieve_obj_permission_check: bool = False

    files_remove_enabled: bool = False
    files_remove_path: str = '{id}/files/remove'
    files_remove_info: str = 'remove files of an item', 
    files_remove_request_schemas: list[tuple[str, str, Schema, bool]] = None
    files_remove_response_schemas: dict[int, Schema] = None
    files_remove_custom_permissions_list: list = []
    files_remove_obj_permission_check: bool = False

    delete_enabled: bool = False
    delete_path: str = '{id}/delete'
    delete_info: str = 'delete an item with all its files'
    delete_response_schemas: dict[int, Schema] = None
    delete_custom_permissions_list: list = []
    delete_obj_permission_check: bool = False
```

### Model-Controller Options

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

Configure your URLs to include the API endpoints ([Reference](https://www.eadwincode.github.io/django-ninja-extra)).

Example:

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
That's it! Thanks to [ninja](https://django-ninja.dev/) & [ninja-extra](https://eadwincode.github.io/django-ninja-extra/), now you can see the auto-generated documentation at http://127.0.0.1:8000/api/docs. 

---

## File Handling
Easier than ever!

### Example

To manage file uploads, downloads, deletion etc (via `ArrayField`), follow this approach:

```python
from django.contrib.postgres.fields import ArrayField
from django_swiftapi.crud_operation.file_operations.storage_operations import local_storage
from django_swiftapi.crud_operation.file_operations.files_handlers import Files_Param
from django_swiftapi.crud_operation.file_operations.files_validators import validate_images, validate_file_sizes

# Define file field in your model:
images = ArrayField(
    models.CharField(max_length=200), 
    default=list, 
    size=5, 
    blank=True, 
    null=True
)

# Register it as a file field:
files_fields = ["images"]

# Provide full configuration for how files should be handled:
files_params_list = [
    FilesParam(
        field_name="images",
        access="public",
        storage=local_storage,
        validator_funcs={
            file_sizes_valid: {"limit": 10},  # limit in MB
            images_valid: {}
        }
    ),
]
```

### Configuration

Configure file-handling from inside your [model's file configuration](#file-handling-example), specify a few attributes in setings.py and that's it! No extra work, no nothing. All CRUD functionalities (uploads, downloads, deletions etc) including authentications, permissions, individual-accesses are handled automatically by `django-swiftapi`.

#### For local storage
In your settings.py:

```
PUBLIC_LOCAL_FILE_WRITE_LOCATION = "" # ensure this directory is public in your production server, ex: 'dummy_site_files/public'
PUBLIC_LOCAL_FILE_URL_PREFIX = "/media" # this prefix will be used in the file links, ex: '/media'
PRIVATE_LOCAL_FILE_WRITE_LOCATION = "" # ensure this directory is not publicly accessible in your production server, ex: 'dummy_site_files/private'
MEDIA_ROOT = PUBLIC_LOCAL_FILE_WRITE_LOCATION
MEDIA_URL = '/media/'  # the value '/media/' is necessary for serving files during development according to django-docs
```

#### For AWS S3
First, you need to install boto3 and set some configurations following AWS's official [docs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html#installation)

Then in your settings.py, set these attributes:

```
PUBLIC_AMAZONS3_BUCKET_NAME = ""
PUBLIC_AMAZONS3_FILE_WRITE_LOCATION = ""
PUBLIC_AMAZONS3_FILE_URL_PREFIX = ""
PRIVATE_AMAZONS3_BUCKET_NAME = ""
PRIVATE_AMAZONS3_FILE_WRITE_LOCATION = ""
MEDIA_URL = '/media/'  # the value '/media/' is necessary for serving files during development according to django-docs
```
Done!

### File Operations

The system automatically provides these file operations:

- **Upload**: Files are uploaded during `create` or `update` operations
- **Retrieve**: Download files via `/file/retrieve` endpoint
- **Remove**: Delete specific files via `/files/remove` endpoint

### File Access Control

- **Public files**: Accessible without authentication
- **Private files**: Require authentication and if specified, ownership verification

### Using Your Own Validation
It's super easy. Just define a function (`django-swiftapi` supports both sync & async) and put it into the dictionary variable `validator_funcs` like this:
```python
# Define your validation function
async def your_validator(arg_name=default):
    # if it validates, then return None
    # if it fails to validate, return a single string containing the error message
    return "error occurred"

# Then, use it inside `FilesParam`
validator_funcs={
    file_sizes_valid: {"limit": 5},
    images_valid: {},
    your_validator: {"<arg_name>": <arg_value>}
}
```

### Storage Support
`django-swiftapi` currently supports:
- local storage (`django_swiftapi.crud_operation.file_operations.storage_operations.local_storage`)
- aws s3 storage (`django_swiftapi.crud_operation.file_operations.storage_operations.aws_s3_storage`)

However, if you want to create support for new platforms, you can do it just by inheriting the `BaseStorage` class and defining these methods below:
```python
from django.db.models import Model
from django_swiftapi.crud_operation.file_operations.storage_operations import BaseStorage

class custom_storage_class(BaseStorage):
    async def dir_maker(instance:Model, files_param):
        """
        Create and return the directory path for storing files related to the model instance.
        Used internally by the storage class.
        """
        pass

    async def url_maker(self,  abs_path:str, files_param, source_dir:str=""):
        """
        Generate a URL (or file identifier for private) from the absolute file path.
        Used internally by the storage class.
        """
        pass

    async def _files_writer(self, instance:Model, files_param):
        """
        Write uploaded files to the specified filesystem.

        Args:
            instance (Model): Django model instance.
            files_param (Files_Param): Contains uploaded file list, chunk size, access level, etc.

        Returns:
            Two lists:
            - List of successfully written file URLs.
            - List of failed file names.
        """
        pass

    async def _files_remover(self, instance:Model, files_param, remove_dir=False):
        """
        Remove files or entire directory from the specified filesystem.

        Args:
            instance (Model): Django model instance.
            files_param (Files_Param): Contains file_links to remove.
            remove_dir (bool, optional): Whether to remove the whole directory.

        Returns:
            Two lists:
            - List of successfully removed file links.
            - List of failed file links.
        """
        pass

    async def _files_retriever(self, instance:Model, files_param):
        """
        Yields chunks of file data from the specified path for streaming purposes.

        Args:
            instance (Model): Django model instance.
            files_param (Files_Param): Contains file_links to retrieve.

        Yields:
            Two lists:
            - List of dictionaries mapping file names to file streams for successfully retrieved files.
            - List of failed file names.
        """
        pass
```

---

## Authentication & Permissions
`django_swiftapi` is highly compatible with [django-allauth](#https://docs.allauth.org/en/latest/). So, if you're using django-allauth, you can validate authentications directly in your modelcontrollers.

### Using Built-in Authentication Classes

```python
from ninja_extra import api_controller
from django_swiftapi.modelcontrol.modelcontrollers.base import SwiftBaseModelController
from django_swiftapi.modelcontrol.authenticators.django_allauth import djangoallauth_userauthentication

# Using allauth authentication
@api_controller("/api", permissions=[djangoallauth_userauthentication()])
class MyController(SwiftBaseModelController):
    pass
```

**IMPORTANT NOTE**: Using `@api_controller("/api", permissions=[djangoallauth_userauthentication()])` will enable authentication for all the routes of the corresponding `modelcontroller`. If you wish to allow certain routes to pass without authentication, you can do it simply like this:

```python
from ninja_extra import api_controller, permissions
from django_swiftapi.modelcontrol.modelcontrollers import SwiftBaseModelController
from django_swiftapi.modelcontrol.authenticators.django_allauth import djangoallauth_userauthentication

@api_controller("/api", permissions=[djangoallauth_userauthentication()])
class MyController(SwiftBaseModelController):

    create_enabled= True
    create_custom_permissions_list = [permissions.AllowAny]
```

As simple as that! You can enable this functionality for other routes too or incorporate your own customized authentication classes for each operation, using:
```python
retrieve_one_custom_permissions_list: list = []
filter_custom_permissions_list: list = []
update_custom_permissions_list: list = []
file_retrieve_custom_permissions_list: list = []
files_remove_custom_permissions_list: list = []
delete_custom_permissions_list: list = []
```

### Enabling Object-Level Permissions

If you wish to give object-specific permissions like only the creator of that object can `rerieve`, `filter`, `update`, `remove` or `delete` that object, you can do so like this:
```python
retrieve_one_obj_permission_check = True
filter_obj_permission_check = True
update_obj_permission_check = True
file_retrieve_obj_permission_check = True
files_remove_obj_permission_check = True
delete_obj_permission_check = True
```

Example:

```python
from django_swiftapi.modelcontrol.modelcontrollers import SwiftBaseModelController

class DocumentController(SwiftBaseModelController):
    retrieve_one_obj_permission_check = True  # Only owner can retrieve
    update_obj_permission_check = True        # Only owner can update
    delete_obj_permission_check = True        # Only owner can delete
```

### Customizing Authentication Class

If you're using any other user authentication system, you need to define your own authentication class overriding just one function:
```
from django_swiftapi.modelcontrol.authenticators import BaseUserAuthentication

# Create custom authentication
class CustomAuthentication(BaseUserAuthentication):
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

---

