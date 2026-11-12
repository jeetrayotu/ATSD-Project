from chevron import render
import rich_click as click
from rich import print
from pathlib import Path

current_file = Path(__file__)
current_dir = current_file.parent
parent_dir = current_dir.parent
template = parent_dir / "assets" / "template.mustache"

@click.group()
def main():
    ...

@main.command()
@click.argument("name")
def chevron(name):
    with template.open() as f:
        print(render(f, {"name":name}))

if __name__ == "__main__":
    main()
