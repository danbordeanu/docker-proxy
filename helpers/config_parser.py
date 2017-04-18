import ConfigParser


def check_if_config_exists(config_file):
    try:
        with open(config_file) as f:
            f.read()
    except IOError as e:
        print('no file, no go {0}'.format(e))
        return False
    return True


def config_params(section):
    check_if_config_exists('config.ini')
    config = ConfigParser.ConfigParser()
    config.read('config.ini')
    dict_ini = {}
    options = config.options(section)
    for option in options:
        try:
            dict_ini[option] = config.get(section, option)
            if dict_ini[option] == -1:
                print('skip:{0}'.format(option))
        except:
            assert isinstance(option, object)
            print('exception on {0}'.format(option))
    return dict_ini