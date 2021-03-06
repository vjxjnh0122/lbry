import json
import os
import sys
import colorama
from docopt import docopt
from collections import OrderedDict
from lbrynet import conf
from lbrynet.core import utils
from lbrynet.lbrynet_daemon.auth.client import JSONRPCException, LBRYAPIClient
from lbrynet.lbrynet_daemon.Daemon import LOADING_WALLET_CODE, Daemon
from lbrynet.core.system_info import get_platform
from jsonrpc.common import RPCError
from urllib2 import URLError, HTTPError
from httplib import UNAUTHORIZED


def remove_brackets(key):
    if key.startswith("<") and key.endswith(">"):
        return str(key[1:-1])
    return key


def set_flag_vals(flag_names, parsed_args):
    kwargs = OrderedDict()
    for key, arg in parsed_args.iteritems():
        if arg is None:
            continue
        elif key.startswith("--"):
            if remove_brackets(key[2:]) not in kwargs:
                k = remove_brackets(key[2:])
                kwargs[k] = guess_type(arg)
        elif key in flag_names:
            if remove_brackets(flag_names[key]) not in kwargs:
                kwargs[remove_brackets(flag_names[key])] = guess_type(arg)
        elif remove_brackets(key) not in kwargs:
            kwargs[remove_brackets(key)] = guess_type(arg)
    return kwargs


def main():
    if len(sys.argv[1:]):
        method, args = sys.argv[1], sys.argv[2:]
    else:
        print_help()
        return

    if method in ['help', '--help', '-h']:
        if len(args) == 1:
            print_help_for_command(args[0])
        else:
            print_help()
        return

    elif method in ['version', '--version']:
        print utils.json_dumps_pretty(get_platform(get_ip=False))
        return

    if method not in Daemon.callable_methods:
        print_error("\"%s\" is not a valid command." % method)
        return

    fn = Daemon.callable_methods[method]
    if hasattr(fn, "_flags"):
        flag_names = fn._flags
    else:
        flag_names = {}

    parsed = docopt(fn.__doc__, args)
    kwargs = set_flag_vals(flag_names, parsed)
    colorama.init()
    conf.initialize_settings()
    api = LBRYAPIClient.get_client()

    try:
        status = api.status()
    except URLError as err:
        if isinstance(err, HTTPError) and err.code == UNAUTHORIZED:
            print_error("Daemon requires authentication, but none was provided.",
                        suggest_help=False)
        else:
            print_error("Could not connect to daemon. Are you sure it's running?",
                        suggest_help=False)
        return 1

    if status['startup_status']['code'] != "started":
        print "Daemon is in the process of starting. Please try again in a bit."
        message = status['startup_status']['message']
        if message:
            if (
                status['startup_status']['code'] == LOADING_WALLET_CODE
                and status['blockchain_status']['blocks_behind'] > 0
            ):
                message += '. Blocks left: ' + str(status['blockchain_status']['blocks_behind'])
            print "  Status: " + message
        return 1

    # TODO: check if port is bound. Error if its not

    try:
        result = api.call(method, **kwargs)
        if isinstance(result, basestring):
            # printing the undumped string is prettier
            print result
        else:
            print utils.json_dumps_pretty(result)
    except (RPCError, KeyError, JSONRPCException, HTTPError) as err:
        error_data = None
        if isinstance(err, HTTPError):
            error_body = err.read()
            try:
                error_data = json.loads(error_body)
            except ValueError:
                print (
                    "There was an error, and the response was not valid JSON.\n" +
                    "Raw JSONRPC response:\n" + error_body
                )
                return 1

            print_error(error_data['error']['message'] + "\n", suggest_help=False)
        else:
            print_error("Something went wrong\n", suggest_help=False)

        print_help_for_command(method)

        if 'data' in error_data['error'] and 'traceback' in error_data['error']['data']:
            print "Here's the traceback for the error you encountered:"
            print "\n".join(error_data['error']['data']['traceback'])
        return 1


def guess_type(x):
    if not isinstance(x, (unicode, str)):
        return x
    if x in ('true', 'True', 'TRUE'):
        return True
    if x in ('false', 'False', 'FALSE'):
        return False
    if '.' in x:
        try:
            return float(x)
        except ValueError:
            # not a float
            pass
    try:
        return int(x)
    except ValueError:
        return x


def print_help_suggestion():
    print "See `{} help` for more information.".format(os.path.basename(sys.argv[0]))


def print_error(message, suggest_help=True):
    error_style = colorama.Style.BRIGHT + colorama.Fore.RED
    print error_style + "ERROR: " + message + colorama.Style.RESET_ALL
    if suggest_help:
        print_help_suggestion()


def print_help():
    commands = Daemon.callable_methods.keys()
    print "\n".join([
        "NAME",
        "   lbrynet-cli - LBRY command line client.",
        "",
        "USAGE",
        "   lbrynet-cli <command> [<args>]",
        "",
        "EXAMPLES",
        "   lbrynet-cli commands            # list available commands",
        "   lbrynet-cli status              # get daemon status",
        "   lbrynet-cli resolve_name what   # resolve a name",
        "   lbrynet-cli help resolve_name   # get help for a command",
        "",
        "COMMANDS",
        wrap_list_to_term_width(commands, prefix='   ')
    ])


def print_help_for_command(command):
    fn = Daemon.callable_methods.get(command)
    if fn:
        print "Help for %s method:\n%s" % (command, fn.__doc__)


def wrap_list_to_term_width(l, width=None, separator=', ', prefix=''):
    if width is None:
        try:
            _, width = os.popen('stty size', 'r').read().split()
            width = int(width)
        except:
            pass
        if not width:
            width = 80

    lines = []
    curr_line = ''
    for item in l:
        new_line = curr_line + item + separator
        if len(new_line) + len(prefix) > width:
            lines.append(curr_line)
            curr_line = item + separator
        else:
            curr_line = new_line
    lines.append(curr_line)

    ret = prefix + ("\n" + prefix).join(lines)
    if ret.endswith(separator):
        ret = ret[:-len(separator)]
    return ret


if __name__ == '__main__':
    sys.exit(main())
