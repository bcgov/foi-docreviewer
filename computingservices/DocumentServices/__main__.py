from logging_config import configure_logging



if __name__ == '__main__':
    configure_logging()
    from rstreamio.reader import documentservicestreamreader

    documentservicestreamreader.app()
