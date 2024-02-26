# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'komanawa-gw-age-tools'
copyright = '2024, Matt Dumont'
author = 'Matt Dumont'
release = 'v2.0.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
extensions = ['sphinx.ext.todo', 'sphinx.ext.viewcode', 'sphinx.ext.autodoc',
              'sphinx.ext.autosummary']
extensions.append('autoapi.extension')

# Auto API settings
autoapi_keep_files = True  # Keep the generated files (for debugging)
autoapi_ignore = []  # Ignore these files
autoapi_python_class_content = 'both'  # Include both the class docstring and the __init__ docstring
autoapi_dirs = ['../src/komanawa/gw_age_tools']  # The directory to process
autoapi_options = ['members', 'inherited-members', 'show-inheritance', 'show-module-summary', 'imported-members',
                   'show-inheritance-diagram']

autoapi_python_use_implicit_namespaces = True  # Use implicit namespaces

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# todo autoapi isn't generating the module overview

# -- options for autodoc -----------------------------------------------------
add_module_names = False  # Don't add the module name to the class/function name
toc_object_entries_show_parents = 'hide'  # Hide the parent class in the TOC

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']
html_sidebars = {'**': [
    'globaltoc.html', # add global api
    'localtoc.html',
    'searchbox.html']}