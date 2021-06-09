# SPDX-FileCopyrightText: © 2020 Matt Williams <matt@milliams.com>
# SPDX-License-Identifier: MIT

import operator
import re
from typing import Iterable, List, Mapping

import lark


__ALL__ = ["match_dict", "filter_dicts"]


def create_parser() -> lark.Lark:
    """
    This function implements a the filter language used by Google Cloud as described at
    https://cloud.google.com/sdk/gcloud/reference/topic/filters

    Returns: the parser object
    """
    grammar = """
    ?start: _expression

    _expression: term
               | parenthesised
               | logical_binary
               | logical_unary

    logical_unary: unary_logical_operator _expression
    ?logical_binary: _expression binary_logical_operator _expression (binary_logical_operator _expression)*

    ?parenthesised: "(" _expression ")"

    unary_logical_operator: "NOT"      -> not
    binary_logical_operator: "AND"     -> and
                           | "OR"      -> or
                           | WS_INLINE -> and

    LIST_COMPARATOR: ":("
                   | "=("
    VALUE_COMPARATOR: ":"
                    | "="
                    | "!="
                    | "<"
                    | "<="
                    | ">"
                    | ">="
                    | "~"
                    | "!~"

    term: "- " KEY ":" "*"                   -> not_defined
        | KEY ":" "*"                        -> is_defined
        | KEY VALUE_COMPARATOR _value        -> compare
        | KEY LIST_COMPARATOR list_items ")" -> compare_list

    _LIST_SEPARATOR: (WS | ",")

    list_items: _value (_LIST_SEPARATOR _value)*

    KEY: CNAME("."CNAME)*
    _value: NUMBER
         | CHARACTER_SEQUENCE
         | STRING

    STRING : /("(?!"").*?(?<!\\\\)(\\\\\\\\)*?"|'(?!'').*?(?<!\\\\)(\\\\\\\\)*?')/i

    CHARACTER_SEQUENCE: (LETTER | NUMBER | "-" | "^" | ":" | "[" | "]" | "@" | "."
                      | "*" | "!" | "£" | "$" | "%" | "*" | "|" | "\\\\" | "/" | "_"
                      | "+" | "=" | "{" | "}" | ":" | ";" | "~" | "#" | "<" | ">" | "?")+

    %import common.LETTER
    %import common.NUMBER
    %import common.CNAME
    %import common.WS_INLINE
    %import common.WS
    %ignore WS_INLINE
    """
    return lark.Lark(grammar)


def parse_filter(filter_text: str) -> lark.Tree:
    """
    Args:
        filter_text: the filter string to parse

    Returns: the parse tree
    """
    return PARSER.parse(filter_text)


@lark.v_args(inline=True)
class FilterDict(lark.Transformer):
    def __init__(self, instance: Mapping):
        super().__init__()
        self.instance = instance

    @staticmethod
    def _pattern_match(true_value: str, check_value: str):
        if check_value.endswith("*"):
            # TODO implement wildcard * prefix matches
            raise NotImplementedError("Pattern prefix matching not implemented")
        return check_value in true_value.split()

    def _key_value(self, key: str):
        true_value = self.instance
        for key in key.split("."):
            true_value = true_value[str(key)]
        return true_value

    def compare_list(
        self, key: lark.Token, operator_name: lark.Token, list_items: lark.Tree
    ):
        try:
            true_value = self._key_value(key)
        except KeyError:
            # If a dotted name does not exist on the instance, return false
            # Perhaps this should be smarter and e.g. return True on ``not_equals``
            return False

        operator_f = {":(": self._pattern_match, "=(": operator.eq}[operator_name]

        check_values = [str(v) for v in list_items.children]

        return any(operator_f(true_value, v) for v in check_values)

    def compare(self, key: lark.Token, operator_name: lark.Token, value: lark.Token):
        try:
            true_value = self._key_value(key)
        except KeyError:
            # If a dotted name does not exist on the instance, return false
            # Perhaps this should be smarter and e.g. return True on ``not_equals``
            return False

        operator_f = {
            ":": self._pattern_match,
            "<": operator.lt,
            "<=": operator.le,
            "=": operator.eq,
            "!=": operator.ne,
            ">=": operator.ge,
            ">": operator.gt,
            "~": lambda s, p: bool(re.match(p, s)),
            "!~": lambda s, p: not bool(re.match(p, s)),
        }[operator_name]

        # Strip the start and end `"` or `'`
        if value.type == "STRING":
            value = value.update("CHARACTER_SEQUENCE", value[1:-1])

        return operator_f(true_value, value)

    def is_defined(self, dotted_key_name: lark.Token):
        d = self.instance
        try:
            for key in dotted_key_name.split("."):
                d = d[key]
        except KeyError:
            return False
        else:
            return True

    def not_defined(self, dotted_key_name: lark.Token):
        return not self.is_defined(dotted_key_name)

    def logical_unary(self, unary_operator: lark.Tree, data: bool):
        if unary_operator.data == "not":
            return not data
        else:
            raise NotImplementedError(
                f"Unary operator {unary_operator.data} not implemented"
            )

    @lark.v_args(inline=False)
    def logical_binary(self, tree):
        data: List[bool] = tree[0::2]
        operators: List[lark.Tree] = tree[1::2]
        all_and = all(t.data == "and" for t in operators)
        all_or = all(t.data == "or" for t in operators)
        if not (all_and or all_or):
            raise SyntaxError("Ambiguous binary operators")
        if all_and:
            return all(data)
        if all_or:
            return any(data)

        raise NotImplementedError("Boolean operator not implmented")


PARSER = create_parser()


def match_dict(pattern: str, dictionary: dict) -> bool:
    """
    Given a filter pattern and a dictionary, does the dictionary match the filter

    Args:
        pattern: a https://cloud.google.com/sdk/gcloud/reference/topic/filters compatible filter string
        dictionary: a (nested) dictionary you wish to filter

    Returns: True if the pattern matches and False otherwise
    """
    p = parse_filter(pattern)
    try:
        return FilterDict(dictionary).transform(p)
    except lark.exceptions.VisitError as e:
        raise e.orig_exc


def filter_dicts(pattern: str, dictionaries: Iterable[dict]) -> Iterable[dict]:
    """
    Given a filter pattern and an iterable of dictionaries, return an iterable containing the matched entries.

    Args:
        pattern:a https://cloud.google.com/sdk/gcloud/reference/topic/filters compatible filter string
        dictionaries: an iterable of (nested) dictionaries you wish to filter

    Returns: an iterable of matched dictionaries
    """
    p = parse_filter(pattern)
    try:
        return filter(lambda d: FilterDict(d).transform(p), dictionaries)
    except lark.exceptions.VisitError as e:
        raise e.orig_exc
