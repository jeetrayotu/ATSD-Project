from chevron import render
from collections import defaultdict
from pathlib import Path
from rich import print
from rich.pretty import pprint
import msgspec
import rich_click as click
from collections import namedtuple

# A named tuple of an attribute name and default value.
# The `name` and `default` values for instances of this tuple
# can be accessed using indices or attribute names.
AttributeNameDefault = namedtuple("AttributeNameDefault", "name,default")

def resolve_path(path):
    """
    Expands user directories in Pathlib Path objects and resolves them
    to their absolute path.
    """

    # Convert `path` into a Pathlib Path object if
    # it isn't one already.
    path = path if isinstance(path, Path) else Path(path)

    # Expand user directories and resolve to absolute path.
    return path.expanduser().resolve() if path else path


def Pathback(ctx, param, value):
    """
    Takes a context object, a parameter name, and a parameter value
    and returns a fully-resolved filesystem path. Loops over tuples
    and converts its items as well.
    """

    # If the parameter value is a tuple, resolve its items.
    if isinstance(value, tuple):
        return [resolve_path(item) for item in value]

    # Return a resolved filesystem path.
    return resolve_path(value)

# A `msgspec` structure for a metamodel class attribute,
# storing an id, a name, a type, and a default value.
class MetaModelClassAttribute(msgspec.Struct):
    id: str
    name: str
    type: str
    defaultValue: str

# A `msgspec` structure for a metamodel class,
# storing an id, a name, and a list of metamodel class attributes.
class MetaModelClass(msgspec.Struct):
    id: str
    name: str
    attributes: list[MetaModelClassAttribute]

# A `msgspec` structure for a metamodel relation,
# storing a name and the kind of relationship.
class MetaModelRelation(msgspec.Struct):
    name: str
    kind: str

# A `msgspec` structure for a metamodel enumeration,
# storing a name.
class MetaModelEnumeration(msgspec.Struct):
    name: str

# A `msgspec` structure for a metamodel,
# storing a list of metamodel classes,
# a list of metamodel relations, and
# a list of metamodel enumerations.
class MetaModel(msgspec.Struct):
    classes: list[MetaModelClass]
    relations: list[MetaModelRelation]
    enumerations: list[MetaModelEnumeration]

# A `msgspec` structure for an instance model object,
# storing a class ID, a name, and a dictionary
# of string attribute values.
class InstanceModelObject(msgspec.Struct):
    classId: str
    name: str
    attributeValues: dict[str, str]

# A `msgspec` structure for an instance model,
# storing a name and a list of instance model objects.
class InstanceModel(msgspec.Struct):
    name: str
    objects: list[InstanceModelObject]

# A `msgspec` structure for a model, storing a metamodel
# and a list of instance models.
class Model(msgspec.Struct):
    metaModel: MetaModel
    instanceModels: list[InstanceModel]

# The python file currently running as a Pathlib Path object.
current_file = Path(__file__)

# The directory of the python file currently running
# as a Pathlib Path object.
current_dir = current_file.parent

# The immediate parent directory of the directory
# of the python file currently running
# as a Pathlib Path object.
parent_dir = current_dir.parent

# The assets directory as a Pathlib Path object.
assets_dir = parent_dir / "assets"

# The directory to store generated Arduino C++ files
# as a Pathlib Path object.
# This directory is made if it doesn't exist yet.
generated_dir = parent_dir / "generated"
generated_dir.mkdir(parents=True, exist_ok=True)

# The directory of the mustache and IML model templates
# as a Pathlib Path object.
mustache_template = assets_dir / "template.mustache"
model_template = assets_dir / "template.iml.json"

@click.group()
def main():
    """
    The entrypoint of the `atsd` application.
    """

@main.command()
@click.argument("model", default=resolve_path(model_template), callback=Pathback)
def generate(model: Path):  # pyright: ignore [reportRedeclaration]
    """
    The subcommand to generate the Arduino C++ files.
    Takes an optional path to a IML model file and resolves it into a Pathlib Path.
    """

    # Reads the IML model file into a `msgspec` Model structure.
    model: Model = msgspec.json.decode(model.read_bytes(), type=Model)

    allAttributeValues = {}
    allClassIDs = {}
    for cls in model.metaModel.classes:

        # Ensure that the class ID doesn't already exist
        # in the dictionary of class IDs. If not,
        # add its name and ID.
        assert cls.id not in allClassIDs
        allClassIDs[cls.id] = cls.name

        for attr in cls.attributes:

            # Ensure that the attribute ID doesn't already exist
            # in the dictionary of attribute IDs. If not, get or
            # set its default values before adding it using its
            # name, ID, and default.
            assert attr.id not in allAttributeValues
            default: str = attr.defaultValue
            if not default:
                match attr.type:
                    case "INT":
                        default = "0"
                    case "DOUBLE":
                        default = "0.0"
                    case "STRING":
                        default = ""
            allAttributeValues[attr.id] = AttributeNameDefault(attr.name, default)

    instances = {}
    for instance in model.instanceModels:
        instances[instance.name] = {}

        # Create a dictionary with a default value of 0
        # for all missing keys and add 1 for every
        # occurence of a particular component.
        counts = defaultdict(int)
        for object in instance.objects:
            counts[allClassIDs[object.classId]] += 1

        for object in instance.objects:

            # If more than one instance of a component exists,
            # add the current instance number to the component name.
            # TODO: Does not use multiplicities. This may conflict with
            #       the naming scheme used in the mustache template.
            count = 0
            originalObjectName = objectName = allClassIDs[object.classId]
            if counts[allClassIDs[object.classId]] > 1:
                objectName = f"{originalObjectName}{count}"
                while objectName in instances[instance.name]:
                    count += 1
                    objectName = f"{originalObjectName}{count}"

            # For every attribute of every component in an instance model object,
            # replace the attribute ID with the attribute name, and keep the value.
            instances[instance.name][objectName] = {
                allAttributeValues[k].name: v for k, v in object.attributeValues.items()
            }

    for robot_name, robot_info in instances.items():

        # Set the path of the Arduino C++ file and create its parent diretory.
        robot_file = generated_dir / robot_name / f"{robot_name}.ino"
        robot_file.parent.mkdir(parents=True, exist_ok=True)

        render_data = {}
        for k1, v1 in robot_info.items():

            # This enables or disables sections of the code related to
            # present or missing components.
            render_data[k1] = True

            # Combine the name of the component with a capitalized
            # version of the attribute name, and set its value
            # to the attribute value.
            for k2, v2 in v1.items():
                render_data[k1 + k2[0].upper() + k2[1:]] = v2

        # Read the mustache template and replace all the placeholders with
        # the provided render data, then write it to the Arduino C++ file.
        with mustache_template.open() as f:
            robot_file.write_text(render(f, render_data))

# If running as a script, use the entrypoint.
if __name__ == "__main__":
    main()
