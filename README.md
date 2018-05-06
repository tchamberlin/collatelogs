# `collatelogs`

A simple log collator. That is, given one or more log file paths, collate them together such that they are in chronological order.

## Motivation

In complicated projects, it is common to have an assortment of logs being generated simultaneously. In a perfect world, these would all have the same log format, and thus could be easily collated/reconciled by appending them all and then sorting them.

However, the world is not perfect, and you may be dealing with a variety of log formats, perhaps (and most importantly) even differences in timestamp format. `collatelogs` handles the consumption of logs based on the given regular expressions, then collates them and outputs them in a common format (also configurable).

## Installation

    $ pip install collatelogs

## Usage

This script probably won't work out of the box, unless your log files happen to have a prefix structure that matches one of the regular expressions in the example configuration. So, you'll probably see something like this:

    $ collatelogs PATH_WITH_LOGS/*.log
    <snip>
    ValueError: Line 'some line from the logs' did not match against any of the given regexes!

So, the first thing you will need to do is define information on the expected log prefixes.

### The config file

For ease of use, it is recommended that you create a config file to avoid having to pass a bunch of arguments every time you run the script. An example is included in the repo, at `collatelogs/example_config.yaml`. This will also be installed alongside the package.

The recommended place for a permanent config file is `~/.cl_config.yaml`. Other paths searched are listed in the help.

It is probably easiest to `$ cp example_config.yaml ~/.cl_config.yaml` before beginning to make your changes.

#### `timestamp_output_format` (optional)

The format of the timestamp output. This will have no affect unless `--parse-timestamps` is passed as an argument at runtime, or `parse_timestamps` is set to `True` in the config file.

#### `line_output_format` (required)

A PEP-3101 compliant format string that defines the output format for each line. The keywords here must be a subset of the regex capturing groups _plus_ any keywords contributed by the meta handlers (see below). Put another way: if you try to include keywords here that aren't being captured in each regular expression, you are going to get an error.


#### `log_parsing_info` (required)
then begin replacing the example entries in `log_parsing_info` with your own entries (leaving the examples will only slow down execution if they are never going to match anything).

Each `dict` in the `log_parsing_info` `list` has four possible parts:

* `regex` (required): The regular expression used to parse log lines
* `timestamp_input_format` (optional): The format of the timestamp for lines captured by `regex`. If this is not given, `dateutil.parse` will be used to generically consume the timestamp, but this will be ~5x slower!
* `timestamp_input_timezone` (optional): The timezone that the log timestamps were output in. If this is not given, it defaults to the local timezone of your computer
* `timestamp_output_timezone` (optional): The timezone that the output log timestamps will be in. If this is not given, it defaults to the local timezone of your computer

Note that this must utilize capturing groups such that every keyword in the `line_output_format` format string is represented.


### Creating Regex Prefixes and Output Format Strings

This isn't too hard, provided you have experience with regular expressions.

1. Examine the log and identify the prefix
2. Break it down into useful parts (timestamp, message, etc. -- see config.yaml for examples)
3. Formulate a regular expression that captures these parts into aptly-named groups
4. Formulate a format string that outputs these groups into a sensible format

Let's see an example. Let's say our log lines are of this format:

    2018-04-20 11:30:01 circus[1624] [INFO] circusd-stats stopped

Even without examining the logger that created this, it can be broken down into four parts:

    {
        'timestamp': '2018-04-20 11:30:01'
        'module': 'circus[1624]', # Not technically a module, but close enough
        'level': 'INFO'
        'message': 'circusd-stats stopped'
    }

The above is what the regex should output via its `groupdict`. So, what regular expression will accomplish this? Well, this is actually pulled from `config.yaml`:

    (?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<module>\S+) (?P<level>\S+) (?P<message>.*)

Because this prefix format is delimited by spaces (and I'm not exactly a regex expert), the regex is pretty verbose. I find that a tool such as regex 101 helps a lot: https://regex101.com/r/bTzhf4/1

Now that the regex has been constructed, add it to the config file as per the above section.

### `meta_handlers`

These handle metadata associated with each log file, making it available to `line_output_format` as keyword arguments.

There are currently two available handlers:
* `user`: The owner of the log file
* `filename`: The filename (base name) of the log file

You will see that these are both present in the example `line_output_format`

There's currently no clean way of adding your own, but you can easily hack them into `metahandlers.py` by defining them, then mapping a name to them in `all_meta_handlers`.
