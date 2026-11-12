from chevron import render
import msgspec
from pathlib import Path
from rich import print
from rich.pretty import pprint
import rich_click as click


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
mustache_template = assets_dir / "template.mustache"
model_template = resolve_path(assets_dir / "template.iml.json")


@click.group()
def main(): ...


@main.command()
@click.argument("model", default=resolve_path(model_template), callback=Pathback)
def chevron(model: Path):  # pyright: ignore [reportRedeclaration]
    model: Model = msgspec.json.decode(model.read_bytes(), type=Model)
    allAttributeValues = {}
    for cls in model.metaModel.classes:
        for attr in cls.attributes:
            assert attr.id not in allAttributeValues
            allAttributeValues[attr.id] = attr.name
    # pprint(model)
    instances = {}
    for instance in model.instanceModels:
        instances[instance.name] = {}
        for object in instance.objects:
            instances[instance.name][object.name] = {
                allAttributeValues[k]: v for k, v in object.attributeValues.items()
            }
    pprint(instances)
    with mustache_template.open() as f:
        ...
        # k: str
        # v: dict[str, str]
        # instance = next(iter(instances))
        # print(render(f, { for k, v in intance} | { "robotName" : instance[""] }))


if __name__ == "__main__":
    main()
