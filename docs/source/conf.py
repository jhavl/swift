# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

import os
import re


# -- Project information -----------------------------------------------------

project = 'Swift'
copyright = '2020, Jesse Haviland and Peter Corke'
author = 'Jesse Haviland and Peter Corke'

# Parse version number out of pyproject.toml
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
with open(os.path.join(_root, 'pyproject.toml'), encoding='utf-8') as f:
    pyproject_src = f.read()
    m = re.search(r'^version\s*=\s*"([0-9.]*)"', pyproject_src, re.MULTILINE)
    version = m.group(1) if m else "unknown"

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.todo',
    'sphinx.ext.viewcode',
    'sphinx.ext.mathjax',
    'sphinx.ext.coverage',
    'sphinx.ext.doctest',
    'sphinx.ext.inheritance_diagram',
    'sphinx_autorun',
]

autosummary_generate = True
autodoc_member_order = 'bysource'

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

exclude_patterns = ['test_*']

# options for sphinx_autorun, used for inline examples
autorun_languages = {}
autorun_languages['pycon_output_encoding'] = 'UTF-8'
autorun_languages['pycon_input_encoding'] = 'UTF-8'

# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_rtd_theme'

html_theme_options = {
    'logo_only': False,
    'prev_next_buttons_location': 'both',
    'style_external_links': True,
}
html_last_updated_fmt = '%d-%b-%Y'
show_authors = True

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
html_css_files = [
    'css/custom.css',
]
