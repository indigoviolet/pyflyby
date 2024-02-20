
from __future__ import print_function

from   pyflyby._imports2s       import (SourceToSourceFileImportsTransformation,
                                        SourceToSourceImportBlockTransformation,
                                        fix_unused_and_missing_imports,
                                        replace_star_imports,
                                        reformat_import_statements)
from   pyflyby._importstmt      import Import
from   pyflyby._log             import logger
import six

# These are comm targets that the frontend (lab/notebook) is expected to
# open. At this point, we handle only missing imports and
# formatting imports

MISSING_IMPORTS = "pyflyby.missing_imports"
FORMATTING_IMPORTS = "pyflyby.format_imports"
INIT_COMMS = "pyflyby.init_comms"
TIDY_IMPORTS = "pyflyby.tidy_imports"
PYFLYBY_START_MSG = "# THIS CELL WAS AUTO-GENERATED BY PYFLYBY\n"
PYFLYBY_END_MSG = "# END AUTO-GENERATED BLOCK\n"

pyflyby_comm_targets= [MISSING_IMPORTS, FORMATTING_IMPORTS, TIDY_IMPORTS]

# A map of the comms opened with a given target name.
comms = {}

# TODO: Document the expected contract for the different
# custom comm messages


def in_jupyter():
    from IPython.core.getipython import get_ipython
    ip = get_ipython()
    if ip is None:
        logger.debug("get_ipython() doesn't exist. Comm targets can only"
                     "be added in an Jupyter notebook/lab/console environment")
        return False
    else:
        try:
            ip.kernel.comm_manager
        except AttributeError:
            logger.debug("Comm targets can only be added in Jupyter "
                         "notebook/lab/console environment")
            return False
        else:
            return True


def _register_target(target_name):
    from IPython.core.getipython import get_ipython
    ip = get_ipython()
    comm_manager = ip.kernel.comm_manager
    comm_manager.register_target(target_name, comm_open_handler)


def initialize_comms():
    if in_jupyter():
        for target in pyflyby_comm_targets:
            _register_target(target)
        from ipykernel.comm import Comm
        comm = Comm(target_name=INIT_COMMS)
        msg = {"type": INIT_COMMS}
        logger.debug("Requesting frontend to (re-)initialize comms")
        comm.send(msg)


def remove_comms():
    for target_name, comm in six.iteritems(comms):
        comm.close()
        logger.debug("Closing comm for " + target_name)

def send_comm_message(target_name, msg):
    if in_jupyter():
        try:
            comm = comms[target_name]
        except KeyError:
            logger.debug("Comm with target_name " + target_name + " hasn't been opened")
        else:
            # Help the frontend distinguish between multiple types
            # of custom comm messages
            msg["type"] = target_name
            comm.send(msg)
            logger.debug("Sending comm message for target " + target_name)


def comm_close_handler(comm, message):
    comm_id = message["comm_id"]
    for target, comm in six.iterkeys(comms):
        if comm.comm_id == comm_id:
            comms.pop(target)


def _reformat_helper(input_code, imports):
    if PYFLYBY_START_MSG in input_code:
        before, bmarker, middle = input_code.partition(PYFLYBY_START_MSG)
    else:
        before, bmarker, middle = "", "", input_code

    if PYFLYBY_END_MSG in middle:
        middle, emarker, after = middle.partition(PYFLYBY_END_MSG)
    else:
        middle, emarker, after = middle, "", ""

    if imports is not None:
        transform = SourceToSourceFileImportsTransformation(middle)

        if isinstance(imports, str):
            imports = [imports]

        for imp in imports:
            assert isinstance(imp, str)
            if not imp.strip():
                continue
            transform.add_import(Import(imp))
        middle = str(transform.output())

    return reformat_import_statements(before + bmarker + middle + emarker + after)

def extract_import_statements(text):
    """This is a util for notebook interactions and extracts import statements
    from some python code. This function also re-orders imports.
    Args:
        code (str): The code from which import statements have to be extracted

    Returns:
        (str, str): The first returned value contains all the import statements.
        The second returned value is the remaining code after
        extracting the import statements.
    """
    transformer = SourceToSourceFileImportsTransformation(text)
    imports = '\n'.join([str(im.pretty_print()).strip() for im in transformer.import_blocks])
    remaining_code = "\n".join([str(st.pretty_print()).strip() if not isinstance(st, SourceToSourceImportBlockTransformation) else "" for st in transformer.blocks])
    return imports, remaining_code

def collect_code_with_imports_on_top(imports: str, cell_array):
    return (
        imports
        + "\n"
        + "\n".join(
            [
                cell["text"] if cell["type"] == "code" and not cell.get("ignore", False) else ""
                for cell in cell_array
            ]
        )
    )

def run_tidy_imports(code):
    return str(
        reformat_import_statements(
            fix_unused_and_missing_imports(
                replace_star_imports(code)
            )
        )
    )

def comm_open_handler(comm, message):
    """
    Handles comm_open message for pyflyby custom comm messages.
    https://jupyter-client.readthedocs.io/en/stable/messaging.html#opening-a-comm.

    Handler for all PYFLYBY custom comm messages that are opened by the frontend
    (at this point, just the jupyterlab frontend does this).

    """

    comm.on_close(comm_close_handler)
    comms[message["content"]["target_name"]] = comm

    @comm.on_msg
    def _recv(msg):
        data = msg["content"]["data"]
        if data["type"] == FORMATTING_IMPORTS:
            msg_id = data.get("msg_id", None)
            imports = data.get("imports", None)
            fmt_code = _reformat_helper(data["input_code"], imports)
            comm.send(
                {
                    "msg_id": msg_id,
                    "formatted_code": str(fmt_code),
                    "type": FORMATTING_IMPORTS,
                }
            )
        elif data["type"] == TIDY_IMPORTS:
            checksum = data.get("checksum", '')
            cell_array = data.get("cellArray", [])
            # import_statements is a string because when
            # SourceToSourceFileImportsTransformation is run on a piece of code
            # it will club similar imports together and re-order the imports
            # by making the imports a string, all the imports are processed
            # together making sure tidy-imports has context on all the imports
            # while clubbing similar imports and re-ordering them.
            import_statements, processed_cell_array = "", []
            for cell in cell_array:
                ignore = False
                text = cell.get("text")
                cell_type = cell.get("type")
                if cell_type == "code":
                    try:
                        imports, text = extract_import_statements(text)
                        import_statements += (imports + "\n")
                    except SyntaxError:
                        # If a cell triggers Syntax Error, we set ignore to
                        # True and don't include it when running tidy-imports
                        # For eg. this is triggered due to cells with magic
                        # commands
                        ignore = True
                processed_cell_array.append({"text": text, "type": cell_type, "ignore": ignore})
            code_with_collected_imports = collect_code_with_imports_on_top(import_statements, processed_cell_array)
            code_post_tidy_imports = run_tidy_imports(code_with_collected_imports)
            import_statements, _ = extract_import_statements(code_post_tidy_imports)
            comm.send(
                {
                    "checksum": checksum,
                    "type": TIDY_IMPORTS,
                    "cells": processed_cell_array,
                    "imports": import_statements,
                }
            )
