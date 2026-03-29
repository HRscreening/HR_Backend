from jinja2 import Environment, FileSystemLoader, select_autoescape
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

env = Environment(
    loader=FileSystemLoader(os.path.join(BASE_DIR, "templates")),
    autoescape=select_autoescape(["html", "xml"]),
    cache_size=50   # optional but good
)


def render_template(template_path: str, context: dict) -> str:
    try:
        template = env.get_template(template_path)
        return template.render(**context)
    except Exception as e:
        print("ACTUAL ERROR:", str(e))  
        raise RuntimeError(f"Template rendering failed: {template_path}") from e