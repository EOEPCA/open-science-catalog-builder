# open-science-catalog-builder

Open Science Catalog (OSC) builder utilities.

This project provides CLI programs that allows the transformation of science project metadata.

## Installation

In order to install the OSC builder, `pip` can be used:

```bash
pip install .
```

## Usage

When installed, the `osc` script is available:


```bash
$ osc
Usage: osc [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  build
  convert
```

It uses the subcommands `convert` and `build`.


### `convert`

This command transforms the original metadata CSVs into an intermediate structure of JSON files.

```bash
$ osc convert --help
Usage: osc convert [OPTIONS] VARIABLES_FILE THEMES_FILE PROJECTS_FILE
                   PRODUCTS_FILE

Options:
  -o, --out-dir TEXT
  --help              Show this message and exit.
```

This command requires the input CSVs for variables, themes, projects and products in order to create the output structure. The output directory can be specified using the `-o` option.

```bash
$ osc convert Variables.csv Themes.csv Projects.csv Products.csv -o out
$ tree out
out/
├── products
│   ├── product-100.json
│   ├── product-101.json
│   ├── product-102.json
│   ├── product-103.json
│   └── ...
├── projects
│   ├── project-100.json
│   ├── project-101.json
│   ├── project-102.json
│   ├── project-103.json
│   └── ...
├── themes
│   ├── atmosphere.json
│   ├── cryosphere.json
│   ├── land.json
│   ├── magnetosphere-ionosphere.json
│   ├── oceans.json
│   └── solid-earth.json
└── variables
    ├── 13-ch4-delta.json
    ├── 13-co2-delta.json
    ├── 13-co-delta.json
    ├── 14-ch4-delta.json
    ├── 14-co2-delta.json
    ├── 14-co-number-concentration.json
    ├── accumulated-precipitation-over-24-h.json
    ├── aerosol-absorption-optical-depth.json
    └── ...
```

# `build`

This command actually creates a static STAC catalog from the given intermediate structure. This static catalog can then be published on a web server for final usage.

```bash
$ osc build --help
Usage: osc build [OPTIONS] DATA_DIR

Options:
  -o, --out-dir TEXT
  -r, --root-href TEXT
  --pretty-print / --no-pretty-print
  --add-iso / --no-add-iso
  --help                          Show this message and exit.
```

```bash
$ osc build --no-add-iso -o build --pretty-print -r http://some-catalog.com ../open-science-catalog-metadata/data/
```

