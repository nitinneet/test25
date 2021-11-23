"""
Copyright 2020 The Magma Authors.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree.

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import argparse
import json
import os
import sys
import time

from firebase_admin import credentials, db, initialize_app


def publish_report(worker_id, build_id, verdict, report):
    # Read Firebase service account config from envirenment
    firebase_config = os.environ["FIREBASE_SERVICE_CONFIG"]
    config = json.loads(firebase_config)

    cred = credentials.Certificate(config)
    initialize_app(cred, {
        'databaseURL': 'https://magma-ci-default-rtdb.firebaseio.com/'
    })

    report_dict = {}
    report_dict[build_id] = {
        'report': report,
        'timestamp': int(time.time()),
        'verdict': verdict,
        }

    ref = db.reference('/workers')
    reports_ref = ref.child(worker_id).child('reports')
    reports_ref.set(report_dict)


def html_url_redirect(url):
    return '<!DOCTYPE html>'\
           '<html>'\
           ' <head>'\
           '  <title>HTML Meta Tag</title>'\
           '  <meta http-equiv = "refresh" content = "0; url = ' + url + '" />'\
           ' </head>'\
           ' <body>'\
           '  <p>Redirecting to another URL</p>'\
           ' </body>'\
           '</html>'\



def lte_integ_test(args):
    # Prepare HTML report with URL redirect
    print(args)
    report = html_url_redirect(args.url)
    print(report)
    publish_report('lte_integ_test', args.build_id, args.verdict == 'success', report)


# create the top-level parser
parser = argparse.ArgumentParser(
    description='Traffic CLI that generates traffic to an endpoint',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)

# Add arguments
parser.add_argument("--build_id", "-id", required=True, help="build ID")
parser.add_argument("--verdict", required=True, help="Test verdict")

# Add subcommands
subparsers = parser.add_subparsers(title='subcommands', dest='cmd')

# create the parser for the "lte" command
parser_lte = subparsers.add_parser('lte')
parser_lte.add_argument("--url", required=True, help="Report URL")
parser_lte.set_defaults(func=lte_integ_test)

# Read arguments from the command line
args = parser.parse_args()
if not args.cmd:
    parser.print_usage()
    sys.exit(1)
args.func(args)
