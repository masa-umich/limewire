import click

from .logger import get_latency_data, plot_latency_data


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("range_name")
def main(range_name: str):
    """Run the latency plotter."""
    data = get_latency_data(range_name, ["fc_timestamp"])
    plot_latency_data(data)


if __name__ == "__main__":
    main()
