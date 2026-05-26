import ast
import importlib
import inspect
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

from app import crud, models, schemas
from app.domains.registry import DOMAIN_ROUTERS
from app.models import (
    admin as model_admin,
    auth as model_auth,
    clubs as model_clubs,
    content as model_content,
    economy as model_economy,
    email as model_email,
    forum as model_forum,
    jobs as model_jobs,
    messaging as model_messaging,
    moderation as model_moderation,
    notifications as model_notifications,
    premium as model_premium,
    portability as model_portability,
    profile as model_profile,
    series as model_series,
    social as model_social,
    stafeta as model_stafeta,
    statistics as model_statistics,
    theatre as model_theatre,
    users as model_users,
    writing as model_writing,
)
from app.schemas import (
    admin as schema_admin,
    audio as schema_audio,
    clubs as schema_clubs,
    common as schema_common,
    economy as schema_economy,
    feedback as schema_feedback,
    forum as schema_forum,
    friends as schema_friends,
    messages as schema_messages,
    notifications as schema_notifications,
    posts as schema_posts,
    premium as schema_premium,
    series as schema_series,
    stafeta as schema_stafeta,
    super_likes as schema_super_likes,
    theatre as schema_theatre,
    users as schema_users,
    writing as schema_writing,
)


ROOT = Path(__file__).resolve().parents[1]

MODEL_MODULES = [
    model_admin,
    model_auth,
    model_clubs,
    model_content,
    model_economy,
    model_email,
    model_forum,
    model_jobs,
    model_messaging,
    model_moderation,
    model_notifications,
    model_premium,
    model_portability,
    model_profile,
    model_series,
    model_social,
    model_stafeta,
    model_statistics,
    model_theatre,
    model_users,
    model_writing,
]

SCHEMA_MODULES = [
    schema_admin,
    schema_audio,
    schema_clubs,
    schema_common,
    schema_economy,
    schema_feedback,
    schema_forum,
    schema_friends,
    schema_messages,
    schema_notifications,
    schema_posts,
    schema_premium,
    schema_series,
    schema_stafeta,
    schema_super_likes,
    schema_theatre,
    schema_users,
    schema_writing,
]


def _local_classes(module):
    return {
        name: value
        for name, value in vars(module).items()
        if inspect.isclass(value) and value.__module__ == module.__name__ and not name.startswith("_")
    }


def _local_public_functions(module):
    return {
        name: value
        for name, value in vars(module).items()
        if inspect.isfunction(value) and value.__module__ == module.__name__ and not name.startswith("_")
    }


def test_models_package_exports_all_mapped_classes():
    mapped_classes = {
        name
        for module in MODEL_MODULES
        for name, value in _local_classes(module).items()
        if hasattr(value, "__tablename__")
    }

    assert set(models.__all__) == {"Base", *mapped_classes}
    for name in mapped_classes:
        assert getattr(models, name).__name__ == name


def test_schemas_package_exports_all_public_schema_types():
    schema_types = {
        name
        for module in SCHEMA_MODULES
        for name, value in _local_classes(module).items()
        if issubclass(value, BaseModel) or issubclass(value, Enum)
    }

    assert schema_types <= set(schemas.__all__)
    assert not [name for name in schemas.__all__ if not hasattr(schemas, name)]
    for name in schema_types:
        assert getattr(schemas, name).__name__ == name
    assert schemas.TheatreRole is schema_theatre.TheatreMemberRole


def test_crud_facade_exports_all_referenced_members():
    missing = []
    for base in (ROOT / "app", ROOT / "tests"):
        for path in base.rglob("*.py"):
            if path == ROOT / "app" / "crud.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "crud"
                    and not hasattr(crud, node.attr)
                ):
                    missing.append(f"{path.relative_to(ROOT)}:{node.lineno} crud.{node.attr}")

    assert missing == []


def _repository_modules_imported_by_domain_facade(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    domain_module_name = ".".join(path.with_suffix("").parts)
    domain_package_parts = domain_module_name.split(".")[:-1]
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node.level:
            package = ".".join(domain_package_parts[: len(domain_package_parts) + 1 - node.level])
            module_name = f"{package}.{node.module}" if package else node.module
        else:
            module_name = node.module
        if module_name.startswith("app.repositories."):
            yield module_name


def test_domain_repository_facades_reexport_imported_repository_apis():
    missing = []
    for facade_path in sorted((ROOT / "app" / "domains").glob("*/repository.py")):
        facade_module = importlib.import_module(".".join(facade_path.relative_to(ROOT).with_suffix("").parts))
        for repository_module_name in _repository_modules_imported_by_domain_facade(facade_path.relative_to(ROOT)):
            repository_module = importlib.import_module(repository_module_name)
            expected_names = set(_local_public_functions(repository_module)) | set(_local_classes(repository_module))
            missing.extend(
                f"{facade_path.relative_to(ROOT)} missing {name} from {repository_module_name}"
                for name in sorted(expected_names)
                if not hasattr(facade_module, name)
            )

    assert missing == []


def test_domain_registry_registers_all_router_modules():
    registered_router_ids = {id(router) for router in DOMAIN_ROUTERS}
    missing = []
    for path in sorted((ROOT / "app" / "routers").glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        defines_router = any(
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "router" for target in node.targets)
            for node in tree.body
        )
        if not defines_router:
            continue
        module = importlib.import_module(".".join(path.relative_to(ROOT).with_suffix("").parts))
        if id(module.router) not in registered_router_ids:
            missing.append(str(path.relative_to(ROOT)))

    assert missing == []


def test_app_modules_import_cleanly():
    failures = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        module_name = ".".join(path.relative_to(ROOT).with_suffix("").parts)
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            failures.append(f"{module_name}: {type(exc).__name__}: {exc}")

    assert failures == []


def test_http_exceptions_are_not_swallowed_by_broad_handlers():
    offenders = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            catches_broad_exception = False
            catches_http_exception = False
            for handler in node.handlers:
                exception_type = handler.type
                name = None
                if isinstance(exception_type, ast.Name):
                    name = exception_type.id
                elif isinstance(exception_type, ast.Attribute):
                    name = exception_type.attr
                if name == "HTTPException":
                    catches_http_exception = True
                if name in {"Exception", "BaseException"} or exception_type is None:
                    catches_broad_exception = True
            if not catches_broad_exception or catches_http_exception:
                continue
            raised_http_lines = []
            for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if not isinstance(child, ast.Raise) or not isinstance(child.exc, ast.Call):
                    continue
                function = child.exc.func
                function_name = None
                if isinstance(function, ast.Name):
                    function_name = function.id
                elif isinstance(function, ast.Attribute):
                    function_name = function.attr
                if function_name == "HTTPException":
                    raised_http_lines.append(child.lineno)
            if raised_http_lines:
                offenders.append(
                    f"{path.relative_to(ROOT)}:{node.lineno} catches broad Exception around HTTPException raises at {raised_http_lines}"
                )

    assert offenders == []
