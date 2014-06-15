#! /usr/bin/env python3

"""
jigsaw-generate.py
Copyright (C) 2014 Julian Gilbey <J.Gilbey@maths.cam.ac.uk>, <jdg@debian.org>
This program comes with ABSOLUTELY NO WARRANTY.
This is free software, and you are welcome to redistribute it
under certain conditions; see the LICENSE file for details.
"""

import random
import sys
import os
import re
import argparse
import subprocess

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

#####################################################################

# Utility functions and global definitions.  These might get moved out
# to separate modules for clarity at some point in the near future.

knowntypes = {
    'smallhexagon',
    'parquet'
}

# LaTeX font sizes
sizes = [r'\tiny',
         r'\scriptsize',
         r'\footnotesize',
         r'\small',
         r'\normalsize',
         r'\large',
         r'\Large',
         r'\LARGE',
         r'\huge',
         r'\Huge'
         ]
normalsize = 4

# Is any entry marked as hidden?
exists_hidden = False

def getopt(layout, data, options, opt, default=None):
    """Determine the value of opt from various possible sources

    Check the command-line options first for this option, then the
    data, then finally the layout; return the first value found, or
    default if the option is not found anywhere.
    """
    if opt in options:
        return options[opt]
    if opt in data:
        return data[opt]
    if opt in layout:
        return layout[opt]
    return default

def losub(text, subs):
    """Substitute <: var :> strings in text using the dict subs"""
    def subtext(matchobj):
        if matchobj.group(1) in subs:
            return subs[matchobj.group(1)]
        else:
            print('Unrecognised substitution: %s' % matchobj.group(0),
                  file=sys.stderr)
    return re.sub(r'<:\s*(\S*)\s*:>', subtext, text)

def make_entry(entry, defaultsize, hide, style):
    """Convert a YAML entry into a LaTeX or Markdown formatted entry

    The YAML entry will either be a simple text entry, or it will be a
    dictionary with required key "text" and optional entries "size"
    and "hidden".

    If there is a "size" key, this will be added to the defaultsize.

    The "hide" parameter can be:
      "hide": the text will be hidden if "hidden" is true
      "mark": the text will be highlighted if "hidden" is true
      "ignore": the "hidden" key will be ignored

    The "style" parameter can be:
      "table": outputs text with no size marker; highlighted hidden
               text will be prepended with "(*)"
      "tikz":  outputs {regular}{size text} or {hidden}{size text},
               where {hidden} highlights the text
      "md":    outputs text for Markdown: highlighted hidden text will
               be prepended with "(*)"; blank text will be replaced by
               "(BLANK)", and all entries will be surrounded on either
               side by a blank space.  There is no size marker.
    """

    if isinstance(entry, dict):
        if 'text' not in entry:
            print('No "text" field in entry in data file.  Rest of data is:\n',
                  file=sys.stderr)
            for f in entry:
                print('  %s: %s\n' % (f, entry[f]), file=sys.stderr)
            return make_entry_util('', '', False, style)
            
        if 'size' in entry:
            try:
                size = defaultsize + int(entry['size'])
                if size < 0:
                    size = 0
                if size >= len(sizes):
                    size = len(sizes) - 1
            except:
                print('Unrecognised size entry for text %(text)s:\n'
                      'size = %(size)s\n'
                      'Defaulting to default size\n' %
                      entry, file=sys.stderr)
                size = defaultsize
        else:
            size = defaultsize

        if 'hidden' in entry and entry['hidden']:
            global exists_hidden
            exists_hidden = True
            if hide == 'hide':
                return make_entry_util('', '', False, style)
            elif hide == 'mark':
                return make_entry_util(entry['text'], sizes[size], True, style)
            elif hide == 'ignore':
                return make_entry_util(entry['text'], sizes[size], False, style)
            else:
                # this shouldn't happen
                sys.exit('This should not happen: bad hide parameter')
        else:
            return make_entry_util(entry['text'], sizes[size], False, style)

    else:
        return make_entry_util(entry, sizes[defaultsize], False, style)

def make_entry_util(text, size, mark_hidden, style):
    """Create the output once the text, size, hide and style are determined

    This should be called with mark_hidden being True or False; hidden
    text should be replaced by '' before this function is called.
    """

    if mark_hidden:
        if style == "table":
            return "(*) %s" % img2tex(text)
        elif style == "tikz":
            return "{hidden}{%s %s}" % (size, img2tex(text))
        elif style == "md":
            return " (*) %s " % text
    else:
        if style == "table":
            return img2tex(text)
        elif style == "tikz":
            return "{regular}{%s %s}" % (size, img2tex(text))
        elif style == "md":
            return " %s " % (text if text else "(BLANK)")

img_re = re.compile(r'!\[([^\]]*)\]\(([^\)]*)\)')

def img2tex(text):
    text = str(text)  # just in case the text is purely numeric
    images = img_re.search(text)
    while images:
        caption, img = images.groups()
        if caption:
            text = img_re.sub(r'\imagecap{%s}{%s}' % (img, caption),
                              text, count=1)
        else:
            text = img_re.sub(r'\image{%s}' % img, text, count=1)

        images = img_re.search(text)

    return text

def cardnum(n):
    """Underline 6 and 9; return everything else as a string"""
    if n in [6, 9]:
        return r'\underline{%s}' % n
    else:
        return str(n)

def make_table(pairs, edges, cards, dsubs, dsubsmd):
    """Create table substitutions for the pairs, edges and cards"""
    dsubs['tablepairs'] = ''
    dsubs['tableedges'] = ''
    dsubs['tablecards'] = ''
    dsubsmd['pairs'] = ''
    dsubsmd['edges'] = ''
    dsubsmd['cards'] = ''

    for p in pairs:
        dsubs['tablepairs'] += ((r'%s&%s\\ \hline' '\n') %
            (make_entry(p[0], normalsize, 'mark', 'table'),
             make_entry(p[1], normalsize, 'mark', 'table')))
        row = '|'
        for entry in p:
            row += make_entry(entry, 0, 'mark', 'md') + '|'
        dsubsmd['pairs'] += row + '\n'
        
    for e in edges:
        dsubs['tableedges'] += ((r'\strut %s\\ \hline' '\n') %
                                make_entry(e, normalsize, 'mark', 'table'))
        dsubsmd['edges'] += '|' + make_entry(e, 0, 'mark', 'md') + '|\n'

    for c in cards:
        dsubs['tablecards'] += ((r'\strut %s\\ \hline' '\n') %
                                make_entry(c, normalsize, 'mark', 'table'))
        dsubsmd['cards'] += '|' + make_entry(c, 0, 'mark', 'md') + '|\n'

def make_triangles(data, layout, pairs, edges, dsubs, dsubsmd):
    """Handle triangular-shaped jigsaw pieces, putting in the Qs and As

    Read the puzzle layout and the puzzle data, and fill in questions
    and answers for any triangular-shaped pieces, preparing the output
    substitution variables in the process.
    """

    puzzle_size = getopt(layout, data, {}, 'puzzleTextSize')
    solution_size = getopt(layout, data, {}, 'solutionTextSize')

    num_triangle_cards = len(layout['triangleSolutionCards'])

    # We read the solution layout from the YAML file, and place the
    # data into our lists.  We don't format them yet, as the
    # formatting may be different for the puzzle and solution

    trianglesolcard = []
    for card in layout['triangleSolutionCards']:
        newcard = []
        for entry in card:
            entrynum = int(entry[1:]) - 1  # -1 to convert to 0-based arrays
            if entry[0] == 'Q':
                newcard.append(pairs[entrynum][0])
            elif entry[0] == 'A':
                newcard.append(pairs[entrynum][1])
            elif entry[0] == 'E':
                newcard.append(edges[entrynum])
            else:
                printf('Unrecognised entry in layout file '
                       '(triangleSolutionCards):\n%s' % card,
                       file=sys.stderr)
        trianglesolcard.append(newcard)

    # List: direction of base side
    trianglesolorient = layout['triangleSolutionOrientation']

    # List: direction of base side, direction of card number (from vertical)
    trianglepuzorient = layout['trianglePuzzleOrientation']

    triangleorder = list(range(num_triangle_cards))
    random.shuffle(triangleorder)

    trianglepuzcard = [[]] * num_triangle_cards

    # We will put solution card i in puzzle position triangleorder[i],
    # rotated by a random amount
    for (i, solcard) in enumerate(trianglesolcard):
        j = triangleorder[i]
        rot = random.randint(0, 2) # anticlockwise rotation
        trianglepuzcard[j] = [solcard[(3 - rot) % 3],
                              solcard[(4 - rot) % 3],
                              solcard[(5 - rot) % 3],
                              cardnum(j + 1), trianglepuzorient[j][1]]
        puzcard = trianglepuzcard[j]
        # What angle does the card number go in the solution?
        # angle of puzzle card + (orientation of sol card - orientation of
        # puz card) - rotation angle [undoing rotation]
        angle = (trianglepuzorient[j][1] +
                 (trianglesolorient[i] - trianglepuzorient[j][0]) -
                 120 * rot)
        solcard.extend([cardnum(j + 1), (angle + 180) % 360 - 180])

        dsubs['trisolcard' + str(i + 1)] = (('{%s}' * 5) %
            (make_entry(solcard[0], solution_size, 'mark', 'tikz'),
             make_entry(solcard[1], solution_size, 'mark', 'tikz'),
             make_entry(solcard[2], solution_size, 'mark', 'tikz'),
             "%s %s" % (sizes[max(solution_size-2, 0)], solcard[3]),
             solcard[4]))
        dsubs['tripuzcard' + str(j + 1)] = (('{%s}' * 5) %
            (make_entry(puzcard[0], puzzle_size, 'hide', 'tikz'),
             make_entry(puzcard[1], puzzle_size, 'hide', 'tikz'),
             make_entry(puzcard[2], puzzle_size, 'hide', 'tikz'),
             "%s %s" % (sizes[max(puzzle_size-2, 0)], puzcard[3]),
             puzcard[4]))

    # For the Markdown version, we only need to record the puzzle cards at
    # this point.

    if 'puzcards3' not in dsubsmd:
        dsubsmd['puzcards3'] = ''
    if 'puzcards4' not in dsubsmd:
        dsubsmd['puzcards4'] = ''

    for t in trianglepuzcard:
        row = '|'
        for entry in t[0:3]:
            row += make_entry(entry, 0, 'hide', 'md') + '|'
        dsubsmd['puzcards3'] += row + '\n'
        dsubsmd['puzcards4'] += row + ' &nbsp; |\n'

    # Testing:
    # for (i, card) in enumerate(trianglesolcard):
    #     print('Sol card %s: (%s, %s, %s), num angle %s' %
    #            (i, card[0], card[1], card[2], card[4]))
    # 
    # for (i, card) in enumerate(trianglepuzcard):
    #     print('Puz card %s: (%s, %s, %s), num angle %s' %
    #            (i, card[0], card[1], card[2], card[3]))

def make_squares(data, layout, pairs, edges, dsubs, dsubsmd):
    """Handle square-shaped jigsaw pieces, putting in the Qs and As

    Read the puzzle layout and the puzzle data, and fill in questions
    and answers for any square-shaped pieces, preparing the output
    substitution variables in the process.

    This is very similar to the make_triangles function.
    """

    puzzle_size = getopt(layout, data, {}, 'puzzleTextSize')
    solution_size = getopt(layout, data, {}, 'solutionTextSize')

    num_triangle_cards = len(layout['triangleSolutionCards'])
    num_square_cards = len(layout['squareSolutionCards'])

    # We read the solution layout from the YAML file, and place the
    # data into our lists.  We don't format them yet, as the
    # formatting may be different for the puzzle and solution

    squaresolcard = []
    for card in layout['squareSolutionCards']:
        newcard = []
        for entry in card:
            entrynum = int(entry[1:]) - 1  # -1 to convert to 0-based arrays
            if entry[0] == 'Q':
                newcard.append(pairs[entrynum][0])
            elif entry[0] == 'A':
                newcard.append(pairs[entrynum][1])
            elif entry[0] == 'E':
                newcard.append(edges[entrynum])
            else:
                printf('Unrecognised entry in layout file '
                       '(squareSolutionCards):\n%s' % card,
                       file=sys.stderr)
        squaresolcard.append(newcard)

    # List: direction of base side
    squaresolorient = layout['squareSolutionOrientation']

    # List: direction of base side, direction of card number (from vertical)
    squarepuzorient = layout['squarePuzzleOrientation']

    squareorder = list(range(num_square_cards))
    random.shuffle(squareorder)

    squarepuzcard = [[]] * num_square_cards

    # We will put solution card i in puzzle position squareorder[i],
    # rotated by a random amount
    for (i, solcard) in enumerate(squaresolcard):
        j = squareorder[i]
        rot = random.randint(0, 3) # anticlockwise rotation
        squarepuzcard[j] = [solcard[(4 - rot) % 4],
                            solcard[(5 - rot) % 4],
                            solcard[(6 - rot) % 4],
                            solcard[(7 - rot) % 4],
                            cardnum(j + num_triangle_cards + 1),
                            squarepuzorient[j][1]]
        puzcard = squarepuzcard[j]
        # What angle does the card number go in the solution?
        # angle of puzzle card + (orientation of sol card - orientation of
        # puz card) - rotation angle [undoing rotation]
        angle = (squarepuzorient[j][1] +
                 (squaresolorient[i] - squarepuzorient[j][0]) -
                 90 * rot)
        solcard.extend([cardnum(j + num_triangle_cards + 1),
                        (angle + 180) % 360 - 180])

        dsubs['sqsolcard' + str(i + 1)] = (('{%s}' * 6) %
            (make_entry(solcard[0], solution_size, 'mark', 'tikz'),
             make_entry(solcard[1], solution_size, 'mark', 'tikz'),
             make_entry(solcard[2], solution_size, 'mark', 'tikz'),
             make_entry(solcard[3], solution_size, 'mark', 'tikz'),
             "%s %s" % (sizes[max(solution_size-2, 0)], solcard[4]),
             solcard[5]))
        dsubs['sqpuzcard' + str(j + 1)] = (('{%s}' * 6) %
            (make_entry(puzcard[0], puzzle_size, 'hide', 'tikz'),
             make_entry(puzcard[1], puzzle_size, 'hide', 'tikz'),
             make_entry(puzcard[2], puzzle_size, 'hide', 'tikz'),
             make_entry(puzcard[3], puzzle_size, 'hide', 'tikz'),
             "%s %s" % (sizes[max(puzzle_size-2, 0)], puzcard[4]),
             puzcard[5]))

    # For the Markdown version, we only need to record the puzzle cards at
    # this point.

    if 'puzcards4' not in dsubsmd:
        dsubsmd['puzcards4'] = ''

    for t in squarepuzcard:
        row = '|'
        for entry in t[0:4]:
            row += make_entry(entry, 0, 'hide', 'md') + '|'
        dsubsmd['puzcards4'] += row + '\n'

    # Testing:
    # for (i, card) in enumerate(squaresolcard):
    #     print('Sol card %s: (%s, %s, %s, %s), num angle %s' %
    #            (i, card[0], card[1], card[2], card[3], card[5]))
    # 
    # for (i, card) in enumerate(squarepuzcard):
    #     print('Puz card %s: (%s, %s, %s), num angle %s' %
    #            (i, card[0], card[1], card[2], card[3], card[4]))

rerun_regex = re.compile(b'rerun ', re.I)

def runlatex(file, options):
    """Run (lua)latex on file"""

    # We may use the options at a later point to specify the LaTeX
    # engine to use, so including it now to reduce amount of code to
    # modify later.
    for count in range(4):
        try:
            output = subprocess.check_output(['lualatex',
                                              '--interaction=nonstopmode',
                                              file])
        except subprocess.CalledProcessError as cpe:
            print("Warning: lualatex %s failed, return value %s" %
                  (file, cpe.returncode), file=sys.stderr)
            print("See the lualatex log file for more details.",
                  file=sys.stderr)
            break

        if not rerun_regex.search(output):
            break


#####################################################################

def main():
    """Process the command line and generate the appropriate output files.

    Command line:
       jigsaw-generate [options] puzzlefile[.yaml]
    There are no options at present, but this will change later.

    We will generate both LaTeX output files and (eventually) a
    markdown file which can be included where needed.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('puzfile', metavar='puzzlefile[.yaml]',
                        help='yaml file containing puzzle data')
    args = parser.parse_args()

    if args.puzfile[-5:] == '.yaml':
        puzfile = args.puzfile
    else:
        puzfile = args.puzfile + '.yaml'
    puzbase = puzfile[:-5]

    # We may well have more options in the future
    options = { 'puzbase': puzbase }

    try:
        infile = open(puzfile)
    except:
        sys.exit('Cannot open %s for reading' % puzfile)

    try:
        data = load(infile, Loader=Loader)
    except yaml.YAMLError as exc:
        if hasattr(exc, 'problem_mark'):
            mark = exc.problem_mark
            sys.exit('Error parsing puzzle data file\n'
                     'Error position: line %s, column %s' %
                     (mark.line+1, mark.column+1))

    if 'type' in data:
        if data['type'] not in knowntypes:
            sys.exit('Unrecognised jigsaw type %s' % data['type'])
    else:
        sys.exit('No jigsaw type found in puzzle file')

    generate_jigsaw(data, options)


def generate_jigsaw(data, options):
    """Generate jigsaw output from data, using options passed to this function.

    Thus function is presently called from main(), but might well be
    called from a GUI at some point in the future, which is why it has
    been separated out.

    When this function is called, data must contain a recognised
    jigsaw type, and the options dictionary must contain an entry
    'puzbase' with the file basename for this particular puzzle.
    """

    # Open template files and layout file.

    # ***FIXME*** At some point, this should be modified to allow for
    # local versions of template files, and also to search in the
    # system directory (wherever that may be) for these files.  At
    # present, they are expected to be in the local directory.

    puztype = data['type']
    puzbase = options['puzbase']

    layoutf = open(puztype + '.yaml')
    try:
        layout = load(layoutf, Loader=Loader)
    except yaml.YAMLError as exc:
        if hasattr(exc, 'problem_mark'):
            mark = exc.problem_mark
            sys.exit('Error parsing puzzle layout file %s.yaml\n'
                     'Error position: line %s, column %s' %
                     (puztype, mark.line+1, mark.column+1))

    # ***FIXME*** The output filenames should be specifiable on the
    # command line.  Also, there should be options for which outputs
    # to produce.

    if 'puzzleTemplateTeX' in layout:
        bodypuz = open(layout['puzzleTemplateTeX']).read()
        outpuzfile = puzbase + '-puzzle.tex'
        outpuz = open(outpuzfile, 'w')
        header = open(layout['puzzleHeaderTeX']).read()
        print(header, file=outpuz)
        puzzletex = True
    else:
        puzzletex = False

    if 'solutionTemplateTeX' in layout:
        bodysol = open(layout['solutionTemplateTeX']).read()
        outsolfile = puzbase + '-solution.tex'
        outsol = open(outsolfile, 'w')
        header = open(layout['solutionHeaderTeX']).read()
        print(header, file=outsol)
        solutiontex = True
    else:
        solutiontex = False

    if 'tableTemplateTeX' in layout:
        bodytable = open(layout['tableTemplateTeX']).read()
        outtablefile = puzbase + '-table.tex'
        outtable = open(outtablefile, 'w')
        header = open(layout['tableHeaderTeX']).read()
        print(header, file=outtable)
        tabletex = True
    else:
        tabletex = False

    if 'puzzleTemplateMarkdown' in layout:
        bodypuzmd = open(layout['puzzleTemplateMarkdown']).read()
        outpuzmdfile = puzbase + '-puzzle.md'
        outpuzmd = open(outpuzmdfile, 'w')
        header = open(layout['puzzleHeaderMarkdown']).read()
        print(header, file=outpuzmd)
        puzzlemd = True
    else:
        puzzlemd = False

    if 'solutionTemplateMarkdown' in layout:
        bodysolmd = open(layout['solutionTemplateMarkdown']).read()
        outsolmdfile = puzbase + '-solution.md'
        outsolmd = open(outsolmdfile, 'w')
        header = open(layout['solutionHeaderMarkdown']).read()
        print(header, file=outsolmd)
        solutionmd = True
    else:
        solutionmd = False

    # These dicts will contain the substitutions needed for the
    # template files; the first is for the LaTeX output files, the
    # second is for the Markdown output files.

    # The Markdown output files are much simpler, as they are intended
    # to be embedded in larger documents, for those who cannot access
    # the PDF files.
    dsubs = dict()
    dsubsmd = dict()

    if 'title' in data:
        dsubs['title'] = data['title']
    else:
        dsubs['title'] = ''
    random.seed(dsubs['title'])

    # Read the card content
    # Three types of cards: pairs, edges, cards (which are single cards
    # for sorting activities)
    if 'pairs' in layout:
        if 'pairs' in data:
            pairs = data['pairs']
            if layout['pairs'] == 0:  # which means any number of pairs
                if len(pairs) == 0:
                    sys.exit('Puzzle type %s needs at least one pair' %
                             layout['typename'])
            else:
                if len(pairs) != layout['pairs']:
                    sys.exit('Puzzle type %s needs exactly %s pairs' %
                             (layout['typename'], layout['pairs']))
        else:
            sys.exit('Puzzle type %s requires pairs in data file' %
                     layout['typename'])
    elif 'pairs' in data:
        sys.exit('Puzzle type %s does not accept pairs in data file' %
                 layout['typename'])
    else:
        pairs = []  # so that later bits of code don't barf

    if 'edges' in layout:
        if 'edges' in data:
            edges = data['edges']
            if len(edges) > layout['edges']:
                print('Warning: more than %s edges given; '
                      'extra will be ignored' % layout['edges'],
                      file=sys.stderr)
                edges = edges[:layout['edges']]
            elif len(edges) < layout['edges']:
                print('Warning: fewer than %s edges given; '
                      'remainder will be blank' % layout['edges'],
                      file=sys.stderr)
                edges += [''] * (layout['edges'] - len(edges))
        else:
            edges = [''] * layout['edges']
    elif 'edges' in data:
        sys.exit('Puzzle type %s does not accept edges in data file' %
                 layout['typename'])
    else:
        edges = []  # so that later bits of code don't barf

    if 'cards' in layout:
        if 'cards' in data:
            cards = data['cards']
            if layout['cards'] == 0:  # which means any number of cards
                if len(cards) == 0:
                    sys.exit('Puzzle type %s needs at least one card' %
                             layout['typename'])
            else:
                if len(cards) != layout['cards']:
                    sys.exit('Puzzle type %s needs exactly %s cards' %
                             (layout['typename'], layout['cards']))
        else:
            sys.exit('Puzzle type %s requires cards in data file' %
                     layout['typename'])
    elif 'cards' in data:
        sys.exit('Puzzle type %s does not accept cards in data file' %
                 layout['typename'])
    else:
        cards = []

    if getopt(layout, data, options, 'shufflePairs'):
        random.shuffle(pairs)
    if getopt(layout, data, options, 'shuffleEdges'):
        random.shuffle(edges)
    if getopt(layout, data, options, 'shuffleCards'):
        random.shuffle(cards)

    # We preserve the original pairs data for the table; we only flip
    # the questions and answers (if requested) for the puzzle cards
    if getopt(layout, data, options, 'flip'):
        flippedpairs = []
        for p in pairs:
            if random.choice([True, False]):
                flippedpairs.append([p[1], p[0]])
            else:
                flippedpairs.append([p[0], p[1]])
    else:
        flippedpairs = pairs

    # The following calls will add the appropriate substitution
    # variables to dsubs and dsubsmd
    global exists_hidden
    exists_hidden = False

    if tabletex or solutionmd:
        make_table(pairs, edges, cards, dsubs, dsubsmd)

    if 'triangleSolutionCards' in layout:
        make_triangles(data, layout, flippedpairs, edges, dsubs, dsubsmd)

    if 'squareSolutionCards' in layout:
        make_squares(data, layout, flippedpairs, edges, dsubs, dsubsmd)

    if exists_hidden:
        dsubs['hiddennotesolution'] = 'Entries that are hidden in the puzzle are highlighted in yellow.'
        dsubs['hiddennotetable'] = 'Entries that are hidden in the puzzle are indicated with (*).'
        dsubsmd['hiddennotemd'] = 'Entries that are hidden in the puzzle are indicated with (*).'
    else:
        dsubs['hiddennotesolution'] = ''
        dsubs['hiddennotetable'] = ''
        dsubsmd['hiddennotemd'] = ''

    dsubs['puzzlenote'] = getopt(layout, data, options, 'note', '')
    dsubsmd['puzzlenote'] = getopt(layout, data, options, 'note', '')

    if tabletex:
        btext = losub(bodytable, dsubs)
        print(btext, file=outtable)
        outtable.close()
        runlatex(outtablefile, options)

    if puzzletex:
        ptext = losub(bodypuz, dsubs)
        print(ptext, file=outpuz)
        outpuz.close()
        runlatex(outpuzfile, options)

    if solutiontex:
        stext = losub(bodysol, dsubs)
        print(stext, file=outsol)
        outsol.close()
        runlatex(outsolfile, options)

    if puzzlemd:
        ptextmd = losub(bodypuzmd, dsubsmd)
        print(ptextmd, file=outpuzmd)
        outpuzmd.close()

    if solutionmd:
        stextmd = losub(bodysolmd, dsubsmd)
        print(stextmd, file=outsolmd)
        outsolmd.close()


# This allows this script to be invoked directly and also (hopefully
# at some later stage) for the functions to be called via a GUI
if __name__ == '__main__':
    main()
