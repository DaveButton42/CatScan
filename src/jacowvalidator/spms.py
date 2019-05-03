"""For verifying that an uploaded file matches an entry from the spms
   references csv file and if so, verifies that the title and authors match """

import os
import csv
import re
from .authors import get_author_list

RE_MULTI_SPACE = re.compile(r' +')

class PaperNotFoundError(Exception):
    """Raised when the paper submitted by a user has no matching entry in the
    spms references list of papers"""
    pass


class ColumnNotFoundError(Exception):
    """Raised when the spms references csv file doesn't have a column this
    function expected"""
    pass


class CSVPathNotDeclared(Exception):
    """Raised when the PATH_TO_JACOW_REFERENCES_CSV environment variable is
    not set"""
    pass


class CSVFileNotFound(Exception):
    """Raised when the file pointed to by the PATH_TO_JACOW_REFERENCES_CSV
    environment variable doesnt exist"""
    pass


# runs conformity checks against the references csv file and returns a dict of
# results, eg: result = { title_match: True, authors_match: False }
def reference_csv_check(filename_minus_ext, title, authors):
    result = {
        'title_match': False, 'authors_match': False,
    }
    if 'PATH_TO_JACOW_REFERENCES_CSV' not in os.environ:
        raise CSVPathNotDeclared("The environment variable "
                                 "PATH_TO_JACOW_REFERENCES_CSV is not "
                                 "set! Unable to locate references.csv file for "
                                 "title checking")
    if not os.path.isfile(os.environ['PATH_TO_JACOW_REFERENCES_CSV']):
        raise CSVFileNotFound(f"No file was found at the location {os.environ['PATH_TO_JACOW_REFERENCES_CSV']}")
    # the encoding value is one that should work for most documents.
    # the encoding for a file can be detected with the command:
    #    ` file -i FILE `
    with open(os.environ['PATH_TO_JACOW_REFERENCES_CSV'], encoding="ISO-8859-1") as f:
        reader = csv.reader(f)
        reading_header_row = True
        match_found = False
        for row in reader:
            if reading_header_row:
                reading_header_row = False
                header = row
                title_col = header.index("title")
                paper_col = header.index("paper")
                authors_col = header.index("authors")
                # confirm those headers existed as expected:
                for heading in ['title_col', 'paper_col', 'authors_col']:
                    # (if they didn't exist, the vars will be undefined)
                    if heading not in locals():
                        raise ColumnNotFoundError(f"could not identify {heading} column in references csv")
            else:
                if filename_minus_ext == row[paper_col]:
                    reference_title = RE_MULTI_SPACE.sub(' ', row[title_col].upper())
                    title_match = title.upper() == reference_title
                    authors_match = authors == row[authors_col]
                    return {
                        'title': {
                            'match': title_match,
                            'docx': title.upper(),
                            'spms': reference_title
                        },
                        'author': {
                            'match': authors_match,
                            'docx': authors,
                            'spms': row[authors_col],
                            'docx_list': get_author_list(authors),
                            'spms_list': get_author_list(row[authors_col]),
                            'report': get_author_list_report(get_author_list(authors),
                                                             get_author_list(row[authors_col]))
                        }
                    }

        # if not returned by now its because the paper wasn't found in the list
        if 'SPMS_DEBUG' in os.environ and os.environ['SPMS_DEBUG'] == 'True':
            return {
                'title': {
                    'match': False,
                    'docx': title.upper(),
                    'spms': 'No matching paper found in the spms csv file'
                },
                'author': {
                    'match': False,
                    'docx': authors,
                    'spms': 'No matching paper found in the spms csv file',
                    'docx_list': list(),
                    'spms_list': list()
                },
            }
        else:
            raise PaperNotFoundError("No matching paper found in the spms csv file")


def get_author_list_report(docx_list, spms_list):
    """Compares two lists of authors (one sourced from the uploaded docx file
    and one sourced from the corresponding paper's entry in the SPMS references
    csv file) and produces a dict array report of the
    form:
        [
            {
            match: True,
            docx: "T. Anderson",
            spms: "T. Anderson"
            },
            {
            match: False,
            docx: "A. Tiller",
            spms: ""
            },
        ]
    """
    # create a copy of spms_list and docx_list so that we can remove items
    #  without mutating the originals:
    spms_authors_to_check = clone_list(spms_list)
    results = list()

    for author in docx_list:
        if author in spms_list:
            results.append({'match': True, 'docx': author, 'spms': author})
            spms_authors_to_check.remove(author)
        else:
            results.append({'match': False, 'docx': author, 'spms': ''})

    # by now any authors remaining in the spms_authors_to_check list are ones
    # that had no matching author in the docx list:
    for author in spms_authors_to_check:
        results.append({'match': False, 'docx': '', 'spms': author})

    return results


def clone_list(list):
    new_list = list()
    for item in list:
        new_list.append(item)
    return new_list
