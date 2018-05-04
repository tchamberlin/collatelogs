# `collatelogs`

A simple log collator. That is, given one or more log file paths, collate them together such that they are in chronological order.

## Motivation

In complicated projects, it is common to have an assortment of logs being generated simultaneously. In a perfect world, these would all have the same log format, and thus could be easily collated/reconciled by appending them all and then sorting them.

However, the world is not perfect, and you may be dealing with a variety of log formats, perhaps (and most importantly) even differences in timestamp format. `collatelogs` handles the consumption of logs based on the given regular expressions, then collates them and outputs them in a common format (also configurable).

## Installation

    $ pip install collatelogs

## Usage

Use default settings; parse given logs. This probably won't work unless your log files happen to have the same prefix structure as those in the examples:

    $ collatelogs PATH_WITH_LOGS/*.log

More likely than not, you will get blank output here. If you run it again with `--bad-line-behavior error`, you will see why:
    
    $ collatelogs PATH_WITH_LOGS/*.log -b error
    Processing log lines:   0%|                                                                                        <snip>
    ValueError: Line '2018-05-03 13:56:00 [32279] | RPCclient::rexec:Connection not yet established, Call not made\n' did not match against any of the given regexes! 

So, you will need to define your own regex(es) to parse your logs.


### Creating Regex Prefixes and Output Format Strings

This isn't too hard, provided you have experience with regular expressions.

1. Examine the log and identify the prefix
2. Break it down into useful parts (timestamp, message, etc. -- see config.yaml for examples)
3. Formulate a regular expression that captures these parts into aptly-named groups
4. Formulate a format string that outputs these groups into a sensible format

Let's see an example. Let's say our log lines are of this format:

    2018-04-20 11:30:01 circus[1624] [INFO] circusd-stats stopped

Even without examining the logger that created this, we can break this down into four parts:
    
    {
        'timestamp': '2018-04-20 11:30:01'
        'module': 'circus[1624]', # Not technically a module, but close enough
        'level': 'INFO'
        'message': 'circusd-stats stopped'
    }

The above is what we want our regex to output via its `groupdict`. So, what regular expression will accomplish this? Well, this is actually pulled from `config.yaml`:
    
    (?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<module>\S+) (?P<level>\S+) (?P<message>.*)

Because this prefix format is delimited by spaces (and I'm not exactly a regex expert), the regex is pretty verbose. I find that a tool such as regex 101 helps a lot: https://regex101.com/r/bTzhf4/1

Anyway, now that we have the regex, we can pass it in via `--prefix-regexes`:

    $ collatelogs PATH_WITH_LOGS/*.log --prefix-regex '(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<module>\S+) (?P<level>\S+) (?P<message>.*)'
    <hopefully sensible output>

Great! But we don't want to type that every time...

### Creating your own `config.yaml`

For ease of use, it is recommended that you create a config file to avoid having to pass a bunch of arguments every time you run the script. An example is included in the repo, at `collatelogs/example_config.yaml`. This will also be installed alongside the package.

The recommended place for a permanent config file is `~/.cl_config.yaml`. Other paths searched are listed in the help.

It is probably easiest to `$ cp example_config.yaml ~/.cl_config.yaml`, wipe out the existing items in the `prefix_regexes` section (they will only slow down execution if they are never going to match anything), then add your regex in their place.
