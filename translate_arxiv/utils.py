from config import config
import sys
import re
import encoding


languageList = '''
Afrikaans            af
Irish                ga
Albanian             sq
Italian              it
Arabic               ar
Japanese             ja
Azerbaijani          az
Kannada              kn
Basque               eu
Korean               ko
Bengali              bn
Latin                la
Belarusian           be
Latvian              lv
Bulgarian            bg
Lithuanian           lt
Catalan              ca
Macedonian           mk
Chinese_Simplified   zh-S
Malay                ms
Chinese_Traditional  zh-T
Maltese              mt
Croatian             hr
Norwegian            no
Czech                cs
Persian              fa
Danish               da
Polish               pl
Dutch                nl
Portuguese           pt
English              en
Romanian             ro
Esperanto            eo
Russian              ru
Estonian             et
Serbian              sr
Filipino             tl
Slovak               sk
Finnish              fi
Slovenian            sl
French               fr
Spanish              es
Galician             gl
Swahili              sw
Georgian             ka
Swedish              sv
German               de
Tamil                ta
Greek                el
Telugu               te
Gujarati             gu
Thai                 th
Haitian_Creole       ht
Turkish              tr
Hebrew               iw
Ukrainian            uk
Hindi                hi
Urdu                 ur
Hungarian            hu
Vietnamese           vi
Icelandic            is
Welsh                cy
Indonesian           id
Yiddish              yi
'''


split = lambda s: re.split(r'\s+', s)


def add_arguments(parser):
    parser.add_argument("-engine", default=config.default_engine, help=f'translation engine, default is {config.default_engine}')
    parser.add_argument("-from", default=config.default_language_from, dest='l_from', help=f'language from, default is {config.default_language_from}')
    parser.add_argument("-to", default=config.default_language_to, dest='l_to', help=f'language to, default is {config.default_language_to}')
    parser.add_argument("-threads", default=config.default_threads, type=int, help='threads for tencent translation, default is auto')
    parser.add_argument("-commands", type=str, help='add commands for translation from a file')
    parser.add_argument("--force-utf8", action='store_true', help='force reading file by utf8')
    parser.add_argument("--list", action='store_true', help='list codes for languages')
    parser.add_argument("--setdefault", action='store_true', help='set default translation engine and languages')
    parser.add_argument("--debug", action='store_true', help='Debug options for developers')
    parser.add_argument("--nocache", action='store_true', help='Debug options for developers')


def process_options(options):

    if options.setdefault:
        print('Translation engine (google or tencent, default google)')
        config.set_variable(config.default_engine_path, config.default_engine_default)
        print('Translation language from (default en)')
        config.set_variable(config.default_language_from_path, config.default_language_from_default)
        print('Translation language to (default zh-CN)')
        config.set_variable(config.default_language_to_path, config.default_language_to_default)
        print('saved!')
        config.load()
        print('engine:', config.default_engine)
        print('language from:', config.default_language_from)
        print('language to:', config.default_language_to)
        sys.exit()

    if options.list:
        print(languageList)
        print('tencent translator does not support some of them')
        sys.exit()

    if options.force_utf8:
        encoding.force_utf8 = True

    if options.threads < 0:
        print('threads must be a non-zero integer number (>=0 where 0 means auto), set to auto')
        options.threads = 0

    additionalCommands = []
    if options.commands:
        content = open(options.commands, 'r').read()
        var = {}
        exec(content, var)
        additionalCommands = var['additional_commands']
    config.mularg_command_list = config.raw_mularg_command_list + additionalCommands

    print("Start")
    print('engine', options.engine)
    print('language from', options.l_from)
    print('language to', options.l_to)

    print('threads', options.threads if options.threads > 0 else 'auto')
    print()