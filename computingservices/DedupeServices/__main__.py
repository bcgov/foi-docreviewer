from services import foiredisdedupeconsumer
from utils.loggingutils import configure_logging



if __name__ == '__main__':
    configure_logging()
    foiredisdedupeconsumer.app()
