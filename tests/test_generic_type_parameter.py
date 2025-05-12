#!/usr/bin/env python

# pyflyby/tests/test_generic_type_parameter.py

# License for THIS FILE ONLY: CC0 Public Domain Dedication
# http://creativecommons.org/publicdomain/zero/1.0/

import pytest
from textwrap import dedent

from pyflyby._imports2s import fix_unused_and_missing_imports
from pyflyby._importdb import ImportDB
from pyflyby._parse import PythonBlock


def test_fix_unused_and_missing_imports_generic_type_parameter():
    """Test that imports are correctly handled for generic type parameters."""
    input = PythonBlock(dedent('''
        from typing import Dict, List

        def process_data(data: Dict[str, List[int]]) -> None:
            for key, values in data.items():
                for value in values:
                    print(f"{key}: {value}")
    ''').lstrip())
    
    db = ImportDB("")
    output = fix_unused_and_missing_imports(input, db=db)
    
    # Both Dict and List should be kept as they're used in type annotations
    expected = PythonBlock(dedent('''
        from typing import Dict, List

        def process_data(data: Dict[str, List[int]]) -> None:
            for key, values in data.items():
                for value in values:
                    print(f"{key}: {value}")
    ''').lstrip())
    
    assert output == expected


def test_fix_unused_and_missing_imports_nested_generic_type():
    """Test handling of deeply nested generic type parameters."""
    input = PythonBlock(dedent('''
        from typing import Dict, List, Tuple, Optional

        def complex_function(
            data: Dict[str, List[Tuple[int, Optional[str]]]]
        ) -> List[Dict[str, int]]:
            result = []
            for key, values in data.items():
                result_dict = {}
                for idx, (num, maybe_str) in enumerate(values):
                    result_dict[key + str(idx)] = num
                result.append(result_dict)
            return result
    ''').lstrip())
    
    db = ImportDB("")
    output = fix_unused_and_missing_imports(input, db=db)
    
    # All type annotations should be preserved
    expected = PythonBlock(dedent('''
        from typing import Dict, List, Optional, Tuple

        def complex_function(
            data: Dict[str, List[Tuple[int, Optional[str]]]]
        ) -> List[Dict[str, int]]:
            result = []
            for key, values in data.items():
                result_dict = {}
                for idx, (num, maybe_str) in enumerate(values):
                    result_dict[key + str(idx)] = num
                result.append(result_dict)
            return result
    ''').lstrip())
    
    assert output == expected


def test_fix_unused_and_missing_imports_imported_generic_type():
    """Test handling imports when the generic type itself is imported."""
    input = PythonBlock(dedent('''
        from typing import Dict, List
        from collections.abc import Sequence, Mapping

        def process_collections(
            seq: Sequence[int],
            maps: Mapping[str, List[Dict[str, int]]]
        ) -> None:
            pass
    ''').lstrip())

    db = ImportDB("")
    output = fix_unused_and_missing_imports(input, db=db)

    # Compare the string representation to avoid formatting differences
    # The output will reformat the imports with alignment, which is expected behavior
    assert "from collections.abc import Mapping, Sequence" in str(output)
    assert "from typing" in str(output)
    assert "import Dict, List" in str(output)


def test_fix_unused_and_missing_imports_unused_generic_type():
    """Test that unused generic types are properly removed."""
    input = PythonBlock(dedent('''
        from typing import Dict, List, Set, Tuple

        # Only Dict and List are used
        def process_data(data: Dict[str, List[int]]) -> None:
            pass
    ''').lstrip())
    
    db = ImportDB("")
    output = fix_unused_and_missing_imports(input, db=db)
    
    # Set and Tuple should be removed
    expected = PythonBlock(dedent('''
        from typing import Dict, List

        # Only Dict and List are used
        def process_data(data: Dict[str, List[int]]) -> None:
            pass
    ''').lstrip())
    
    assert output == expected


def test_fix_unused_and_missing_imports_python312_generics():
    """Test Python 3.12 style generic type parameters."""
    input = PythonBlock(dedent('''
        from typing import Callable, Dict

        # Python 3.12 style generic type syntax
        def process_data(
            data: dict[str, list[int]],
            transformer: Callable[[int], str]
        ) -> None:
            pass
    ''').lstrip())
    
    db = ImportDB("")
    output = fix_unused_and_missing_imports(input, db=db)
    
    # Callable should be kept, but dict and list are builtins
    expected = PythonBlock(dedent('''
        from typing import Callable

        # Python 3.12 style generic type syntax
        def process_data(
            data: dict[str, list[int]],
            transformer: Callable[[int], str]
        ) -> None:
            pass
    ''').lstrip())
    
    assert output == expected