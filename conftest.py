# Prevent pytest from trying to import the root __init__.py as a test module.
# The root __init__.py uses relative imports designed for ComfyUI's loader, not
# for direct execution, so pytest cannot collect it without a parent package.
collect_ignore = ["__init__.py"]
