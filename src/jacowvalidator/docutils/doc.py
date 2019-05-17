import os
from jacowvalidator.docutils.styles import get_style_summary
from jacowvalidator.docutils.margins import get_margin_summary
from jacowvalidator.docutils.languages import get_language_summary
from jacowvalidator.docutils.title import get_title_summary
from jacowvalidator.docutils.authors import get_author_summary
from jacowvalidator.docutils.abstract import get_abstract_summary
from jacowvalidator.docutils.heading import get_heading_summary
from jacowvalidator.docutils.paragraph import get_paragraph_summary, get_all_paragraph_summary
from jacowvalidator.docutils.references import get_reference_summary
from jacowvalidator.docutils.figures import get_figure_summary
from jacowvalidator.docutils.tables import get_table_summary
from jacowvalidator.spms import reference_csv_check, HELP_INFO as SPMS_HELP_INFO, EXTRA_INFO as SPMS_EXTRA_INFO


class AbstractNotFoundError(Exception):
    """Raised when the paper submitted by a user has no matching entry in the
    spms references list of papers"""
    pass


def parse_paragraphs(doc):
    title_index = abstract_index = reference_index = -1

    summary = {}
    for i, p in enumerate(doc.paragraphs):
        # first paragraph is the title
        text = p.text.strip()
        if not text:
            continue

        # first non empty paragraph is the title
        # TODO fix since it can go over more than paragraph
        if title_index == -1:
            title_index = i
            summary['Title'] = get_title_summary(p)

        # find abstract heading
        if text.lower() == 'abstract':
            abstract_index = i
            summary['Abstract'] = get_abstract_summary(p)

        # all headings, paragraphs captions, figures, tables, equations should be between these two
        # if abstract_index > 0 and reference_index == -1:
        #     print(i)
        #     # check if a known jacow style
        #     for section_type, section_data in DETAILS.items():
        #         if 'styles' in section_data:
        #             if p.style.name in section_data['styles']['jacow']:
        #                 found = f"{section_type} - {p.style.name}"
        #                 print(found)
        #                 break
        #             elif p.style.name in section_data['styles']['normal']:
        #                 found = f"{section_type} -- {p.style.name}"
        #                 print(found)
        #                 break
        #         else:
        #             for sub_type, sub_data in section_data.items():
        #                 if p.style.name in sub_data['styles']['jacow']:
        #                     found = f"{section_type} - {sub_type} - {p.style.name}"
        #                     print(found)
        #                 elif 'normal' in sub_data['styles'] and p.style.name in sub_data['styles']['normal']:
        #                     found = f"{section_type} -- {sub_type} -- {p.style.name}"
        #                     print(found)
        #                     break

        # find reference heading
        if text.lower() == 'references':
            reference_index = i
            break

    # if abstract not found
    if abstract_index == -1:
        raise AbstractNotFoundError("Abstract header not found")

    # authors is all the text between title and abstract heading
    summary['Authors'] = get_author_summary(doc.paragraphs[title_index+1: abstract_index])

    return summary


def create_upload_variables(doc, paper_name):
    summary = {}
    doc_summary = parse_paragraphs(doc)

    # get style details
    summary['Styles'] = get_style_summary(doc)
    summary['Margins'] = get_margin_summary(doc)
    summary['Languages'] = get_language_summary(doc)
    summary['List'] = get_all_paragraph_summary(doc)
    summary['Title'] = doc_summary['Title']
    summary['Authors'] = doc_summary['Authors']
    summary['Abstract'] = doc_summary['Abstract']
    summary['Headings'] = get_heading_summary(doc)
    summary['Paragraphs'] = get_paragraph_summary(doc)
    summary['References'] = get_reference_summary(doc)
    summary['Figures'] = get_figure_summary(doc)
    summary['Tables'] = get_table_summary(doc)

    # get title and author to use in SPMS check
    title = summary['Title']['details'][0]
    authors = summary['Authors']['details']

    return summary, authors, title


def create_spms_variables(paper_name, authors, title):
    summary = {}
    if "URL_TO_JACOW_REFERENCES_CSV" in os.environ:
        reference_csv_url = os.environ["URL_TO_JACOW_REFERENCES_CSV"]
        author_text = ''.join([a['text'] + ", " for a in authors])
        reference_csv_details = reference_csv_check(paper_name, title['text'], author_text)
        summary['SPMS'] = {
            'title': 'SPMS Abstract Title Author Check',
            'help_info': SPMS_HELP_INFO,
            'extra_info': SPMS_EXTRA_INFO,
            'ok': reference_csv_details['title']['match'] and reference_csv_details['author']['match'],
            'message': 'SPMS Abstract Title Author Check issues',
            'details': reference_csv_details['summary'],
            'anchor': 'spms'
        }
    else:
        reference_csv_details = False

    return summary, reference_csv_details




