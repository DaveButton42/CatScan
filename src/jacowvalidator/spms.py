"""For verifying that an uploaded file matches an entry from the spms
   references csv file and if so, verifies that the title and authors match """

import os
import json
import csv
import re
from jacowvalidator.docutils.authors import get_author_list
from jacowvalidator.models import Conference

RE_MULTI_SPACE = re.compile(r' +')
HELP_INFO = 'CSESPMSCeck'
EXTRA_INFO = {
    'title':'Title and Author Breakdown',
    'headers': '<thead><tr><th>Type</th><th>Match</th><th>Document</th><th>SPMS</th></tr></thead>',
    'columns': ['type', 'match_ok', 'document', 'spms']
}


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


def get_conference_path(conference_id):
    conference = Conference.query.filter_by(short_name=conference_id).first()
    return os.path.join(os.environ['JACOW_REFERENCES_PATH'], conference.path)


# runs conformity checks against the references csv file and returns a dict of
# results, eg: result = { title_match: True, authors_match: False }
def reference_csv_check(filename_minus_ext, title, authors, conference_path):
    result = {
        'title_match': False, 'authors_match': False,
    }

    # the encoding value is one that should work for most documents.
    # the encoding for a file can be detected with the command:
    #    ` file -i FILE `
    with open(conference_path, encoding="ISO-8859-1") as f:
        reader = csv.reader(f)
        reading_header_row = True
        match_found = False
        for spms_row in reader:
            if reading_header_row:
                reading_header_row = False
                header = spms_row
                title_col = header.index("title")
                paper_col = header.index("paper")
                authors_col = header.index("authors")
                # confirm those headers existed as expected:
                for heading in ['title_col', 'paper_col', 'authors_col']:
                    # (if they didn't exist, the vars will be undefined)
                    if heading not in locals():
                        raise ColumnNotFoundError(f"could not identify {heading} column in references csv")
            else:
                if filename_minus_ext == spms_row[paper_col]:
                    reference_title = RE_MULTI_SPACE.sub(' ', spms_row[title_col].upper())
                    title_match = title.upper().strip('*') == reference_title
                    report, authors_match = get_author_list_report(authors, spms_row[authors_col])

                    # builds the data for display, match_ok determines the colour of the cell
                    # True for green, False for red, 2 for amber.
                    summary_list = [{
                        'type': 'Author',
                        'match_ok': 2 if result['match'] and not result['exact'] else result['match'],
                        'document': result['document'],
                        'spms': result['spms']} for result in report]

                    return {
                        'title': {
                            'match': title_match,
                            'document': title,
                            'spms': reference_title
                        },
                        'author': {
                            'match': authors_match,
                            'document': authors,
                            'spms': spms_row[authors_col],
                            'document_list': get_author_list(authors),
                            'spms_list': get_author_list(spms_row[authors_col]),
                            'report': report
                        },
                        'summary': [{
                            'type': 'Title',
                            'match_ok': title_match,
                            'document': title,
                            'spms': reference_title
                        }, {
                            'type': 'Extracted Author List',
                            'match_ok': authors_match,
                            'document': authors,
                            'spms': spms_row[authors_col],
                        }, *summary_list],
                    }

        # if not returned by now its because the paper wasn't found in the list
        if 'SPMS_DEBUG' in os.environ and os.environ['SPMS_DEBUG'] == 'True':
            return {
                'title': {
                    'match': False,
                    'document': title.upper(),
                    'spms': 'No matching paper found in the spms csv file'
                },
                'author': {
                    'match': False,
                    'document': authors,
                    'spms': 'No matching paper found in the spms csv file',
                    'document_list': list(),
                    'spms_list': list(),
                    'report': list()
                },
                'summary': [{
                    'type': 'title',
                    'match': False,
                    'document': title.upper(),
                    'spms': 'No matching paper found in the spms csv file'
                    }, {
                    'type': 'author',
                    'match': False,
                    'document': authors,
                    'spms': 'No matching paper found in the spms csv file',
                }],

            }
        else:
            raise PaperNotFoundError("No matching paper found in the spms csv file")


def get_author_list_report(document_text, spms_text):
    """Compares two lists of authors (one sourced from the uploaded document file
    and one sourced from the corresponding paper's entry in the SPMS references
    csv file) and produces a dict array report of the form:
        [
            {
            match: True,
            exact: True,
            document: "Y. Z. G??mez Mart??nez",
            spms: "Y. Gomez Martinez"
            },
            {
            match: True,
            exact: False,
            document: "T. X. Therou",
            spms: "T. Therou"
            },
            {
            match: False,
            exact: False,
            document: "A. Tiller",
            spms: ""
            },
        ]
    """
    extracted_document_authors = get_author_list(document_text)
    extracted_spms_authors = get_author_list(spms_text)
    # extracted_document_authors = ['Y. Z. G??mez Mart??nez', 'T. X. Therou', 'A. Tiller']
    document_list = build_comparison_author_objects(extracted_document_authors)
    spms_list = build_comparison_author_objects(extracted_spms_authors)
    # document_list = [
    # {
    #   original-value: 'Y. Z. G??mez Mart??nez',
    #   compare-value: 'Y. Z. Gomez Martinez',
    #   compare-first-last: 'Y. Gomez Martinez',
    #   compare-last: 'Gomez Martinez'
    # }, ... ]

    # create lists needed for matching and sorting:

    spms_matched = list()
    spms_unmatched = list()
    document_matched = list()
    results = list()

    # perform first round of matching, looking for exact matches:

    all_authors_match = True  # assume they all match until left with unpaired authors
    for spms_author in spms_list[:]:
        document_author = next((document_author for document_author in document_list if document_author['compare-value'] == spms_author['compare-value']), None)
        if document_author:
            document_matched.append(document_author)
            document_list.remove(document_author)
            spms_matched.append(spms_author)
            spms_list.remove(spms_author)
            results.append({'document': document_author['original-value'],
                            'spms': spms_author['original-value'],
                            'exact': True,
                            'match': True})
        else:
            spms_unmatched.append(spms_author)
            spms_list.remove(spms_author)

    # Move remaining authors in document_list to document_unmatched:

    document_unmatched = document_list

    # if any unmatched authors remain, perform second round of matching, looking for loose matches (missing initials)

    for spms_author in spms_unmatched[:]:
        document_author = next((document_author for document_author in document_unmatched if document_author['compare-first-last'] == spms_author['compare-first-last'] or document_author['compare-transliterated'] == spms_author['compare-transliterated']), None)
        if document_author:
            document_matched.append(document_author)
            document_unmatched.remove(document_author)
            spms_matched.append(spms_author)
            spms_unmatched.remove(spms_author)
            results.append({'document': document_author['original-value'],
                            'spms': spms_author['original-value'],
                            'exact': False,
                            'match': True})
    # after all matching rounds completed, any authors remaining in the
    # unmatched lists are added to results with a match value of false:

    for spms_author in spms_unmatched:
        results.append({'document': '',
                        'spms': spms_author['original-value'],
                        'exact': False,
                        'match': False})
        all_authors_match = False

    for document_author in document_unmatched:
        results.append({'document': document_author['original-value'],
                        'spms': '',
                        'exact': False,
                        'match': False})
        all_authors_match = False

    return results, all_authors_match


def build_comparison_author_objects(author_names):
    author_compare_objects = list()
    for author in author_names:
        original_value = author
        compare_value = normalize_author_name(author)
        compare_first_last = get_first_last_only(compare_value)
        compare_last = get_surname(compare_first_last)
        compare_transliterated = transliterate_accents(compare_first_last)
        author_compare_objects.append(
            {
                'original-value': original_value,
                'compare-value': compare_value,
                'compare-first-last': compare_first_last,
                'compare-transliterated': compare_transliterated,
                'compare-last': compare_last
            })
    return author_compare_objects


def normalize_author_name(author_name):
    """returns a normalized name suitable for comparing"""
    # ensure periods are followed by a space:
    normalized_name = author_name.replace('.', '. ').replace('  ', ' ')
    # remove hyphens (sometimes inconsistently applied):
    normalized_name = normalized_name.replace('-', '')
    # remove asterisks (sometimes included in document authors text):
    normalized_name = normalized_name.replace('*', '')
    # remove formatting characters occasionally observed:
    normalized_name = normalized_name.replace('???', '')
    # strip possible extra whitespace:
    normalized_name = normalized_name.strip()
    return normalized_name


def get_first_last_only(normalized_author_name):
    """given an author name returns a version with only the first initial
    eg: given 'T. J. Z. Bytes' returns 'T. Bytes' """
    first_intial = normalized_author_name[:2]
    surname = get_surname(normalized_author_name)
    return ' '.join((first_intial, surname))


def get_surname(author_name):
    """finds the index of the last period in the string then returns the substring
    starting 2 positions forward from that period"""
    return author_name[author_name.rfind('.')+2:]


def clone_list(list_to_clone):
    new_list = list()
    for item in list_to_clone:
        new_list.append(item)
    return new_list


def insert_spaces_after_periods(author_list_to_adjust):
    new_list = list()
    for author in author_list_to_adjust:
        fixed_author = author.replace('.', '. ')  # ensure each period is followed by a space
        fixed_author = fixed_author.replace('  ', ' ')  # remove any duplicate spaces that were made
        new_list.append(fixed_author)
    return new_list


def normalize_author_names(author_list_to_clean):
    new_list = list()
    for author in author_list_to_clean:
        new_list.append(normalize_author_name(author))
    return new_list

# below taken from https://stackoverflow.com/questions/6837148/change-foreign-characters-to-their-normal-equivalent
ACCENTED_CHARS_DICT = {'??': 'a', '??': 'A', '??': 'a', '??': 'A', '??': 'a',
                       '??': 'A', '??': 'a', '??': 'A', '??': 'a', '??': 'A',
                       '??': 'a', '??': 'A', '??': 'a', '??': 'A', '??': 'a',
                       '??': 'A', '??': 'ae', '??': 'AE', '??': 'ae', '??': 'AE',
                       '???': 'b', '???': 'B', '??': 'c', '??': 'C', '??': 'c',
                       '??': 'C', '??': 'c', '??': 'C', '??': 'c', '??': 'C',
                       '??': 'c', '??': 'C', '??': 'd', '??': 'D', '???': 'd',
                       '???': 'D', '??': 'd', '??': 'D', '??': 'dh', '??': 'Dh',
                       '??': 'e', '??': 'E', '??': 'e', '??': 'E', '??': 'e',
                       '??': 'E', '??': 'e', '??': 'E', '??': 'e', '??': 'E',
                       '??': 'e', '??': 'E', '??': 'e', '??': 'E', '??': 'e',
                       '??': 'E', '??': 'e', '??': 'E', '???': 'f', '???': 'F',
                       '??': 'f', '??': 'F', '??': 'g', '??': 'G', '??': 'g',
                       '??': 'G', '??': 'g', '??': 'G', '??': 'g', '??': 'G',
                       '??': 'h', '??': 'H', '??': 'h', '??': 'H', '??': 'i',
                       '??': 'I', '??': 'i', '??': 'I', '??': 'i', '??': 'I',
                       '??': 'i', '??': 'I', '??': 'i', '??': 'I', '??': 'i',
                       '??': 'I', '??': 'i', '??': 'I', '??': 'j', '??': 'J',
                       '??': 'k', '??': 'K', '??': 'l', '??': 'L', '??': 'l',
                       '??': 'L', '??': 'l', '??': 'L', '??': 'l', '??': 'L',
                       '???': 'm', '???': 'M', '??': 'n', '??': 'N', '??': 'n',
                       '??': 'N', '??': 'n', '??': 'N', '??': 'n', '??': 'N',
                       '??': 'o', '??': 'O', '??': 'o', '??': 'O', '??': 'o',
                       '??': 'O', '??': 'o', '??': 'O', '??': 'o', '??': 'O',
                       '??': 'oe', '??': 'OE', '??': 'o', '??': 'O', '??': 'o',
                       '??': 'O', '??': 'oe', '??': 'OE', '???': 'p', '???': 'P',
                       '??': 'r', '??': 'R', '??': 'r', '??': 'R', '??': 'r',
                       '??': 'R', '??': 's', '??': 'S', '??': 's', '??': 'S',
                       '??': 's', '??': 'S', '???': 's', '???': 'S', '??': 's',
                       '??': 'S', '??': 's', '??': 'S', '??': 'SS', '??': 't',
                       '??': 'T', '???': 't', '???': 'T', '??': 't', '??': 'T',
                       '??': 't', '??': 'T', '??': 't', '??': 'T', '??': 'u',
                       '??': 'U', '??': 'u', '??': 'U', '??': 'u', '??': 'U',
                       '??': 'u', '??': 'U', '??': 'u', '??': 'U', '??': 'u',
                       '??': 'U', '??': 'u', '??': 'U', '??': 'u', '??': 'U',
                       '??': 'u', '??': 'U', '??': 'u', '??': 'U', '??': 'ue',
                       '??': 'UE', '???': 'w', '???': 'W', '???': 'w', '???': 'W',
                       '??': 'w', '??': 'W', '???': 'w', '???': 'W', '??': 'y',
                       '??': 'Y', '???': 'y', '???': 'Y', '??': 'y', '??': 'Y',
                       '??': 'y', '??': 'Y', '??': 'z', '??': 'Z', '??': 'z',
                       '??': 'Z', '??': 'z', '??': 'Z', '??': 'th', '??': 'Th',
                       '??': 'u', '??': 'a', '??': 'a', '??': 'b', '??': 'b',
                       '??': 'v', '??': 'v', '??': 'g', '??': 'g', '??': 'd',
                       '??': 'd', '??': 'e', '??': 'E', '??': 'e', '??': 'E',
                       '??': 'zh', '??': 'zh', '??': 'z', '??': 'z', '??': 'i',
                       '??': 'i', '??': 'j', '??': 'j', '??': 'k', '??': 'k',
                       '??': 'l', '??': 'l', '??': 'm', '??': 'm', '??': 'n',
                       '??': 'n', '??': 'o', '??': 'o', '??': 'p', '??': 'p',
                       '??': 'r', '??': 'r', '??': 's', '??': 's', '??': 't',
                       '??': 't', '??': 'u', '??': 'u', '??': 'f', '??': 'f',
                       '??': 'h', '??': 'h', '??': 'c', '??': 'c', '??': 'ch',
                       '??': 'ch', '??': 'sh', '??': 'sh', '??': 'sch', '??': 'sch',
                       '??': '', '??': '', '??': 'y', '??': 'y', '??': '', '??': '',
                       '??': 'e', '??': 'e', '??': 'ju', '??': 'ju', '??': 'ja',
                       '??': 'ja'}


def transliterate_accents(name):
    name_copy = name
    for letter in name:
        if ord(letter) > 127:
            if letter in ACCENTED_CHARS_DICT:
                name_copy = name_copy.replace(letter, ACCENTED_CHARS_DICT[letter])
    return name_copy
