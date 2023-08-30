from typing import List

from lxml.builder import ElementMaker
from lxml import etree

from .types import Theme, Variable, EOMission

nsmap = {
    "gmd": "http://www.isotc211.org/2005/gmd",
    "gmx": "http://www.isotc211.org/2005/gmx",
    "gco": "http://www.isotc211.org/2005/gco",
    "gml": "http://www.opengis.net/gml/3.2",
    "xlink": "http://www.w3.org/1999/xlink",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

GMX = ElementMaker(namespace=nsmap["gmx"], nsmap=nsmap)
GML = ElementMaker(namespace=nsmap["gml"], nsmap=nsmap)
GMD = ElementMaker(namespace=nsmap["gmd"], nsmap=nsmap)
GCO = ElementMaker(namespace=nsmap["gco"], nsmap=nsmap)


def build_codelists(
    themes: List[Theme],
    variables: List[Variable],
    eo_missions: List[EOMission],
) -> etree._ElementTree:
    # create codelists.xml
    root = GMX(
        "CT_CodelistCatalogue",
        GMX("name", GCO("CharacterString", "OSC_Codelists")),
        GMX(
            "scope",
            GCO("CharacterString", "Codelists for Open Science Catalog"),
        ),
        GMX(
            "fieldOfApplication",
            GCO("CharacterString", "Open Science Catalog")
        ),
        GMX("versionNumber", GCO("CharacterString", "1.0.0")),
        GMX("versionDate", GCO("Date", "2022-02-05")),
        GMX(
            "language",
            GMD(
                "LanguageCode",
                "English",
                codeList="#LanguageCode",
                codeListValue="eng",
            ),
        ),
        GMX(
            "characterSet",
            GMD(
                "MD_CharacterSetCode",
                "utf8",
                codeList="#MD_CharacterSetCode",
                codeListValue="utf8",
            ),
        ),
        # actual codelists for themes, variables
        GMX(
            "codeListItem",
            *[
                GMX(
                    "codeEntry",
                    GMX(
                        "CodeDefinition",
                        GML(
                            "identifier",
                            f"OSC_Theme_{theme.name}",
                            codeSpace="OSC",
                        ),
                        GML("description", theme.description),
                        GML(
                            "descriptionReference",
                            **{
                                f"{{{nsmap['xlink']}}}type": "simple",
                                f"{{{nsmap['xlink']}}}href": theme.link,
                            },
                        ),
                        **{f"{{{nsmap['gml']}}}id": f"OSC_Theme_{theme.name}"},
                    ),
                )
                for theme in themes
            ],
        ),
        GMX(
            "codeListItem",
            *[
                GMX(
                    "codeEntry",
                    GMX(
                        "CodeDefinition",
                        GML(
                            "identifier",
                            f"OSC_Variable_{variable.name}",
                            codeSpace="OSC",
                        ),
                        GML("description", variable.description),
                        GML(
                            "descriptionReference",
                            **{
                                f"{{{nsmap['xlink']}}}type": "simple",
                                f"{{{nsmap['xlink']}}}href": variable.link,
                            },
                        ),
                        **{
                            f"{{{nsmap['gml']}}}id":
                                f"OSC_Variable_{variable.name}"
                        },
                    ),
                )
                for variable in variables
            ],
        ),
        GMX(
            "codeListItem",
            *[
                GMX(
                    "codeEntry",
                    GMX(
                        "CodeDefinition",
                        GML(
                            "identifier",
                            f"OSC_EO_Mission_{eo_mission.name}",
                            codeSpace="OSC",
                        ),
                        GML("description", eo_mission.name),
                        # GML(
                        #     "descriptionReference",
                        #     **{
                        #         f"{{{nsmap['xlink']}}}type": "simple",
                        #         f"{{{nsmap['xlink']}}}href": eo_mission.name,
                        #     },
                        # ),
                        **{
                            f"{{{nsmap['gml']}}}id":
                                f"OSC_EO_Mission_{eo_mission.name}"
                        },
                    ),
                )
                for eo_mission in eo_missions
            ],
        ),
    )

    return etree.ElementTree(root)
