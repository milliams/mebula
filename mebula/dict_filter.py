import operator
import re
from typing import List, Mapping, Union

import lark  # type: ignore


def parse_filter(filter_text: str) -> lark.Tree:
    """
    https://cloud.google.com/sdk/gcloud/reference/topic/filters
    """
    grammar = """
    start: _expression

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

    term: "- " KEY ":" "*"                                  -> not_defined
        | KEY ":" "*"                                       -> is_defined
        | KEY VALUE_COMPARATOR value                        -> compare
        | KEY LIST_COMPARATOR value (_LIST_SEPARATOR value)* ")" -> compare_list

    _LIST_SEPARATOR: (WS | ",")

    KEY: CNAME("."CNAME)*
    value: NUMBER
         | CHARACTER_SEQUENCE
         | STRING

    STRING : /[ubf]?r?("(?!"").*?(?<!\\\\)(\\\\\\\\)*?"|'(?!'').*?(?<!\\\\)(\\\\\\\\)*?')/i

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
    parser = lark.Lark(grammar)
    return parser.parse(filter_text)


class FilterInstance(lark.Transformer):
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

    def start(self, tree: List[lark.Tree]):
        return all(tree)

    def compare_list(self, tree: List[Union[lark.Tree, lark.Token]]):
        keys = tree[0]
        try:
            true_value = self._key_value(keys)
        except KeyError:
            # If a dotted name does not exist on the instance, return false
            # Perhaps this should be smarter and e.g. return True on ``not_equals``
            return False

        operator_name = tree[1]
        operator_f = {":(": self._pattern_match, "=(": operator.eq}[operator_name]

        check_values = [str(v.children[0]) for v in tree[2:]]

        return any(operator_f(true_value, v) for v in check_values)

    def compare(self, tree: List[Union[lark.Tree, lark.Token]]):
        keys = tree[0]
        try:
            true_value = self._key_value(keys)
        except KeyError:
            # If a dotted name does not exist on the instance, return false
            # Perhaps this should be smarter and e.g. return True on ``not_equals``
            return False

        operator_name = tree[1]
        operator_f = {
            ":": self._pattern_match,
            "<": operator.lt,
            "<=": operator.le,
            "=": operator.eq,
            "!=": operator.ne,
            ">=": operator.ge,
            ">": operator.gt,
            "~": lambda s, p: re.match(p, s),
            "!~": lambda s, p: not re.match(p, s),
        }[operator_name]

        check_value = tree[2].children[0]

        return operator_f(true_value, check_value)

    def is_defined(self, tree: List[lark.Tree]):
        key = tree[0]  # TODO dotted names
        try:
            self.instance[key]
        except KeyError:
            return False
        else:
            return True

    def not_defined(self, tree: List[lark.Tree]):
        return not self.is_defined(tree)

    def logical_unary(self, tree: List[lark.Tree]):
        if tree[0].data == "not":
            return not tree[1]
        else:
            raise NotImplementedError(f"Unary operator {tree[0].data} not implemented")

    def logical_binary(self, tree: List[lark.Tree]):
        data = tree[0::2]
        operators = tree[1::2]
        all_and = all(t.data == "and" for t in operators)
        all_or = all(t.data == "or" for t in operators)
        if not (all_and or all_or):
            raise Exception("Ambiguous binary operators")
        if all_and:
            return all(data)
        if all_or:
            return any(data)

        raise NotImplementedError("Boolean operator not implmented")