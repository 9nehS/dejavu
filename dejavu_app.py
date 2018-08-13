#!/usr/bin/env python

import os
import sys
import json
import warnings
import argparse

from flask import Flask, jsonify, request, abort, flash, redirect, url_for
from werkzeug.utils import secure_filename

from dejavu import Dejavu
from dejavu.recognize import FileRecognizer
from dejavu.recognize import MicrophoneRecognizer
from argparse import RawTextHelpFormatter

warnings.filterwarnings("ignore")

DEFAULT_CONFIG_FILE = "dejavu.cnf.SAMPLE"
DEFAULT_APP_HOST = '0.0.0.0'
UPLOAD_FOLDER = '/tmp/dejavu/uploads'
ALLOWED_EXTENSIONS = set(['wav', 'mp3', 'm4a'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024    # Limit the maximum allowed payload to 10 megabytes


def init(configpath):
    """ 
    Load config from a JSON file
    """
    try:
        with open(configpath) as f:
            config = json.load(f)
    except IOError as err:
        print("Cannot open configuration: %s. Exiting" % (str(err)))
        sys.exit(1)

    # create a Dejavu instance
    return Dejavu(config)


@app.route('/icetest/dejavu/help')
def help():
    return jsonify(
        {
            '[GET]Print help info': '/icetest/dejavu/help',
            '[GET]List fingerprinted audio': '/icetest/dejavu/audio/list',
            '[POST]Fingerprint audio': '/icetest/dejavu/audio/fingerprint',
            '[POST]Recognize audio': '/icetest/dejavu/audio/recognize'
        })


@app.route('/icetest/dejavu/audio/list')
def list_audio():
    global djv
    return jsonify(list(djv.db.get_songs()))


@app.route('/icetest/dejavu/audio/fingerprint', methods=['POST'])
def fingerprint():
    global djv
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            return json_msg('Error', 'No file part in message posted')
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            return json_msg('Error', 'No selected file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            abs_filename = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(abs_filename)
            # return json_msg('Success', abs_filename)
            result = djv.fingerprint_file(abs_filename)
            if result == Dejavu.FINGERPRINT_STATUS_SUCCESS:
                return json_msg('Success', 'Fingerprint succeed')
            elif result == Dejavu.FINGERPRINT_STATUS_FILE_EXISTED:
                return json_msg('Warning', 'File fingerprint existed')

    return json_msg('Error', 'Some error occurred during fingerprint')


@app.route('/icetest/dejavu/audio/recognize', methods=['POST'])
def recognize():
    global djv
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            return json_msg('Error', 'No file part in message posted')
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            return json_msg('Error', 'No selected file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            abs_filename = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(abs_filename)
            # return json_msg('Success', abs_filename)
            result = djv.recognize(FileRecognizer, abs_filename)
            return jsonify(result) if result is not None else json_msg('Warning', 'No audio matched')

    return json_msg('Error', 'Some error occurred during fingerprint')


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def json_msg(result=None, msg=None):
    dict_msg = {'result': result,
                'message': msg}
    return jsonify(dict_msg)


def main():
    parser = argparse.ArgumentParser(
        description="Dejavu: Audio Fingerprinting library",
        formatter_class=RawTextHelpFormatter)
    parser.add_argument('-c', '--config', nargs='?',
                        help='Path to configuration file\n'
                             'Usages: \n'
                             '--config /path/to/config-file\n')
    parser.add_argument('-f', '--fingerprint', nargs='*',
                        help='Fingerprint files in a directory\n'
                             'Usages: \n'
                             '--fingerprint /path/to/directory extension\n'
                             '--fingerprint /path/to/directory')
    parser.add_argument('-r', '--recognize', nargs=2,
                        help='Recognize what is '
                             'playing through the microphone\n'
                             'Usage: \n'
                             '--recognize mic number_of_seconds \n'
                             '--recognize file path/to/file \n')
    parser.add_argument('-l', '--listen', nargs='?', const='5000',
                        help='Listen on port(default 5000) as WEB service\n'
                             'Usages: \n'
                             '--listen port_number(e.g.8080)\n')
    args = parser.parse_args()

    if args.listen:
        print("Now dejavu will run in WEB service mode and '-f'/'-r' will be ignored")

        config_file = args.config
        if config_file is None:
            config_file = DEFAULT_CONFIG_FILE
            # print "Using default config file: %s" % (config_file)

        global djv
        djv = init(config_file)

        print(list(djv.db.get_songs()))
        app.run(host=DEFAULT_APP_HOST, port=int(args.listen))

        sys.exit(0)
    else:
        if not args.fingerprint and not args.recognize:
            parser.print_help()
            sys.exit(0)

        config_file = args.config
        if config_file is None:
            config_file = DEFAULT_CONFIG_FILE
            # print "Using default config file: %s" % (config_file)

        djv = init(config_file)
        if args.fingerprint:
            # Fingerprint all files in a directory
            if len(args.fingerprint) == 2:
                directory = args.fingerprint[0]
                extension = args.fingerprint[1]
                print("Fingerprinting all .%s files in the %s directory"
                      % (extension, directory))
                djv.fingerprint_directory(directory, ["." + extension], 4)

            elif len(args.fingerprint) == 1:
                filepath = args.fingerprint[0]
                if os.path.isdir(filepath):
                    print("Please specify an extension if you'd like to fingerprint a directory!")
                    sys.exit(1)
                djv.fingerprint_file(filepath)

        elif args.recognize:
            # Recognize audio source
            song = None
            source = args.recognize[0]
            opt_arg = args.recognize[1]

            if source in ('mic', 'microphone'):
                song = djv.recognize(MicrophoneRecognizer, seconds=opt_arg)
            elif source == 'file':
                song = djv.recognize(FileRecognizer, opt_arg)
            print(song)

        sys.exit(0)


if __name__ == '__main__':
    main()
