from chevron import render
import msgspec
from pathlib import Path
from rich import print
from rich.pretty import pprint
import rich_click as click
from collections import defaultdict


def resolve_path(path):
    path = path if isinstance(path, Path) else Path(path)
    return path.expanduser().resolve() if path else path


def Pathback(ctx, param, value):
    if isinstance(value, tuple):
        return [resolve_path(item) for item in value]
    return resolve_path(value)


class MetaModelClassAttribute(msgspec.Struct):
    id: str
    name: str


class MetaModelClass(msgspec.Struct):
    id: str
    name: str
    attributes: list[MetaModelClassAttribute]


class MetaModelRelation(msgspec.Struct):
    name: str
    kind: str


class MetaModelEnumeration(msgspec.Struct):
    name: str


class MetaModel(msgspec.Struct):
    classes: list[MetaModelClass]
    relations: list[MetaModelRelation]
    enumerations: list[MetaModelEnumeration]


class InstanceModelObject(msgspec.Struct):
    classId: str
    name: str
    attributeValues: dict[str, str]


class InstanceModel(msgspec.Struct):
    name: str
    objects: list[InstanceModelObject]


class Model(msgspec.Struct):
    metaModel: MetaModel
    instanceModels: list[InstanceModel]


current_file = Path(__file__)
current_dir = current_file.parent
parent_dir = current_dir.parent
assets_dir = parent_dir / "assets"
generated_dir = parent_dir / "generated"
generated_dir.mkdir(parents=True, exist_ok=True)
mustache_template = assets_dir / "template.mustache"
model_template = resolve_path(assets_dir / "template.iml.json")


@click.group()
def main(): ...


@main.command()
@click.argument("model", default=resolve_path(model_template), callback=Pathback)
def generate(model: Path):  # pyright: ignore [reportRedeclaration]
    model: Model = msgspec.json.decode(model.read_bytes(), type=Model)
    allAttributeValues = {}
    allClassIDs = {}
    for cls in model.metaModel.classes:
        assert cls.id not in allClassIDs
        allClassIDs[cls.id] = cls.name
        for attr in cls.attributes:
            assert attr.id not in allAttributeValues
            allAttributeValues[attr.id] = attr.name
    # pprint(model)
    instances = {}
    for instance in model.instanceModels:
        instances[instance.name] = {}
        counts = defaultdict(int)
        for object in instance.objects:
            counts[allClassIDs[object.classId]] += 1
        for object in instance.objects:
            count = 0
            originalObjectName = objectName = allClassIDs[object.classId]
            if counts[allClassIDs[object.classId]] > 1:
                objectName = f"{originalObjectName}{count}"
                while objectName in instances[instance.name]:
                    count += 1
                    objectName = f"{originalObjectName}{count}"
            instances[instance.name][objectName] = {
                allAttributeValues[k]: v for k, v in object.attributeValues.items()
            }
    for robot_name, robot_info in instances.items():
        robot_file = generated_dir / robot_name / f"{robot_name}.ino"
        robot_file.parent.mkdir(parents=True, exist_ok=True)
        render_data = {k1 + k2[0].upper() + k2[1:]:v2 for k1, v1 in robot_info.items() for k2, v2 in v1.items() }
        with mustache_template.open() as f:
            robot_file.write_text(render(f, render_data))


if __name__ == "__main__":
    main()
