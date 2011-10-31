import sublime, sublime_plugin
from vintage import transform_selection
from vintage import transform_selection_regions

class ViMoveByCharactersInLine(sublime_plugin.TextCommand):
    def run(self, edit, forward = True, extend = False, visual = False):
        delta = 1 if forward else -1

        transform_selection(self.view, lambda pt: pt + delta, extend=extend,
            clip_to_line=(not visual))

class ViMoveByCharacters(sublime_plugin.TextCommand):
    def advance(self, delta, visual, pt):
        pt += delta
        if not visual and self.view.substr(pt) == '\n':
            pt += delta

        return pt

    def run(self, edit, forward = True, extend = False, visual = False):
        delta = 1 if forward else -1
        transform_selection(self.view, lambda pt: self.advance(delta, visual, pt),
            extend=extend)

class ViMoveToHardEol(sublime_plugin.TextCommand):
    def run(self, edit, repeat = 1, extend = False):
        repeat = int(repeat)
        if repeat > 1:
            for i in xrange(repeat - 1):
                self.view.run_command('move',
                    {'by': 'lines', 'extend': extend, 'forward': True})

        transform_selection(self.view, lambda pt: self.view.line(pt).b,
            extend=extend, clip_to_line=False)

class ViMoveToFirstNonWhiteSpaceCharacter(sublime_plugin.TextCommand):
    def first_character(self, pt):
        l = self.view.line(pt)
        lstr = self.view.substr(l)

        offset = 0
        for c in lstr:
            if c == ' ' or c == '\t':
                offset += 1
            else:
                break

        return l.a + offset

    def run(self, edit, extend = False):
        transform_selection(self.view, lambda pt: self.first_character(pt),
            extend=extend)


g_last_move_command = None

class ViMoveToCharacter(sublime_plugin.TextCommand):
    def find_next(self, forward, char, before, pt):
        lr = self.view.line(pt)

        extra = 0 if before else 1

        if forward:
            line = self.view.substr(sublime.Region(pt, lr.b))
            idx = line.find(char, 1)
            if idx >= 0:
                return pt + idx + 1 * extra
        else:
            line = self.view.substr(sublime.Region(lr.a, pt))[::-1]
            idx = line.find(char, 0)
            if idx >= 0:
                return pt - idx - 1 * extra

        return pt

    def run(self, edit, character, extend = False, forward = True, before = False, record = True):
        if record:
            global g_last_move_command
            g_last_move_command = {'character': character, 'extend': extend,
                'forward':forward, 'before':before}

        transform_selection(self.view,
            lambda pt: self.find_next(forward, character, before, pt),
            extend=extend)

# Helper class used to implement ';'' and ',', which repeat the last f, F, t
# or T command (reversed in the case of ',')
class SetRepeatMoveToCharacterMotion(sublime_plugin.TextCommand):
    def run_(self, args):
        if args:
            return self.run(**args)
        else:
            return self.run()

    def run(self, reverse = False):
        if g_last_move_command:
            cmd = g_last_move_command.copy()
            cmd['record'] = False
            if reverse:
                cmd['forward'] = not cmd['forward']

            self.view.run_command('set_motion', {
                'motion': 'vi_move_to_character',
                'motion_args': cmd,
                'inclusive': True })

class ViMoveToBrackets(sublime_plugin.TextCommand):
    def move_by_percent(self, percent):
        destination = int(self.view.rowcol(self.view.size())[0] * (percent / 100.0))
        destination = self.view.line(self.view.text_point(destination, 0)).a
        destination = advance_while_white_space_character(self.view, destination)

        transform_selection(self.view, lambda pt: destination)

    def run(self, edit, repeat=1):
        repeat = int(repeat)
        if repeat == 1:
            bracket_chars = ")]}"
            def adj(pt):
                if (self.view.substr(pt) in bracket_chars):
                    return pt + 1
                else:
                    return pt
            transform_selection(self.view, adj)
            self.view.run_command("move_to", {"to": "brackets", "extend": True, "force_outer": True})
        else:
            self.move_by_percent(repeat)

class ViGotoLine(sublime_plugin.TextCommand):
    def run(self, edit, repeat = 1, explicit_repeat = True, extend = False):
        repeat = int(repeat)
        if not explicit_repeat:
            self.view.run_command('move_to', {'to': 'eof', 'extend':extend})
        else:
            target_pt = self.view.text_point(repeat - 1, 0)
            transform_selection(self.view, lambda pt: target_pt,
                extend=extend)

def advance_while_white_space_character(view, pt, white_space="\t "):
    while view.substr(pt) in white_space:
        pt += 1

    return pt

class MoveCaretToScreenCenter(sublime_plugin.TextCommand):
    def run(self, edit, extend = True):
        screenful = self.view.visible_region()

        row_a = self.view.rowcol(screenful.a)[0]
        row_b = self.view.rowcol(screenful.b)[0]

        middle_row = (row_a + row_b) / 2
        middle_point = self.view.text_point(middle_row, 0)

        middle_point = advance_while_white_space_character(self.view, middle_point)
        transform_selection(self.view, lambda pt: middle_point, extend=extend)

class MoveCaretToScreenTop(sublime_plugin.TextCommand):
    def run(self, edit, repeat, extend = True):
        # Don't modify offset so not fully visible regions have a lower chance
        # of scrolling the screen.
        # lines_offset = int(repeat) - 1
        lines_offset = int(repeat)
        screenful = self.view.visible_region()

        target = screenful.begin()
        for x in xrange(lines_offset):
            current_line = self.view.line(target)
            target = current_line.b + 1

        target = advance_while_white_space_character(self.view, target)
        transform_selection(self.view, lambda pt: target, extend=extend)

class MoveCaretToScreenBottom(sublime_plugin.TextCommand):
    def run(self, edit, repeat, extend = True):
        # Don't modify offset so not fully visible regions have a lower chance
        # of scrolling the screen.
        # lines_offset = int(repeat) - 1
        lines_offset = int(repeat)
        screenful = self.view.visible_region()

        target = screenful.end()
        for x in xrange(lines_offset):
            current_line = self.view.line(target)
            target = current_line.a - 1
        target = self.view.line(target).a

        target = advance_while_white_space_character(self.view, target)
        transform_selection(self.view, lambda pt: target, extend=extend)

def expand_to_whitespace(view, r):
    a = r.a
    b = r.b
    while view.substr(b) in " \t":
        b += 1

    if b == r.b:
        while view.substr(a - 1) in " \t":
            a -= 1

    return sublime.Region(a, b)

class ViExpandToWords(sublime_plugin.TextCommand):
    def run(self, edit, outer = False, repeat = 1):
        repeat = int(repeat)
        transform_selection_regions(self.view, lambda r: sublime.Region(r.b + 1, r.b + 1))
        self.view.run_command("move", {"by": "stops", "extend":False, "forward":False, "word_begin":True, "punct_begin":True})
        for i in xrange(repeat):
            self.view.run_command("move", {"by": "stops", "extend":True, "forward":True, "word_end":True, "punct_end":True})
        if outer:
            transform_selection_regions(self.view, lambda r: expand_to_whitespace(self.view, r))

class ViExpandToBigWords(sublime_plugin.TextCommand):
    def run(self, edit, outer = False, repeat = 1):
        repeat = int(repeat)
        transform_selection_regions(self.view, lambda r: sublime.Region(r.b + 1, r.b + 1))
        self.view.run_command("move", {"by": "stops", "extend":False, "forward":False, "word_begin":True, "punct_begin":True, "separators": ""})
        for i in xrange(repeat):
            self.view.run_command("move", {"by": "stops", "extend":True, "forward":True, "word_end":True, "punct_end":True, "separators": ""})
        if outer:
            transform_selection_regions(self.view, lambda r: expand_to_whitespace(self.view, r))

class ViExpandToQuotes(sublime_plugin.TextCommand):
    def compare_quote(self, character, p):
        if self.view.substr(p) == character:
            return self.view.score_selector(p, "constant.character.escape") == 0
        else:
            return False

    def expand_to_quote(self, character, r):
        p = r.b
        a = p
        b = p
        while a >= 0 and not self.compare_quote(character, a):
            a -= 1

        sz = self.view.size()
        while p < sz and not self.compare_quote(character, b):
            b += 1

        return sublime.Region(a + 1, b)

    def expand_to_outer(self, r):
        a, b = r.a, r.b
        if a > 0:
            a -= 1
        if b < self.view.size():
            b += 1
        return expand_to_whitespace(self.view, sublime.Region(a, b))

    def run(self, edit, character, outer = False):
        transform_selection_regions(self.view, lambda r: self.expand_to_quote(character, r))
        if outer:
            transform_selection_regions(self.view, lambda r: self.expand_to_outer(r))

class ViExpandToTag(sublime_plugin.TextCommand):
    def run(self, edit, outer = False):
        self.view.run_command('expand_selection', {'to': 'tag'})
        if outer:
            self.view.run_command('expand_selection', {'to': 'tag'})

class ViExpandToBrackets(sublime_plugin.TextCommand):
    def run(self, edit, character, outer = False):
        self.view.run_command('expand_selection', {'to': 'brackets', 'brackets': character})
        if outer:
            self.view.run_command('expand_selection', {'to': 'brackets', 'brackets': character})
