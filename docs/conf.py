project = "Faster SAM"
author = "Dotz"
release = "0.14.0"

extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "alabaster"
html_static_path = ["_static"]

python_maximum_signature_line_length = 10
autodoc_typehints = "none"
