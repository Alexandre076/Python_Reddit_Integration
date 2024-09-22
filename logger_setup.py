# logger_setup.py
import logging

def setup_logging(log_file='db//activity.log'):
    """
    Set up the logging configuration.

    Parameters:
        log_file (str, optional): The file path to save the log messages. Defaults to 'activity.log'.

    Returns:
        None

    This function configures the logging module to save log messages to a file. The log messages will be appended to the file if it already exists. The log messages will be formatted with the timestamp, log level, and the message. Only log messages with a level of INFO or higher will be saved.

    Example usage:
        setup_logging('my_log.log')
    """
    logging.basicConfig(
        filename=log_file,
        filemode='a',  # Append to the log file
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO  # Log INFO and higher-level messages
    )

# Function to log and print messages (reuse this in your other scripts)
def log_and_print(message, level='info'):
    """
    Logs a message and prints it to the console.

    Args:
        message (str): The message to log and print.
        level (str, optional): The log level. Defaults to 'info'.

    Returns:
        None

    This function logs a message with the specified log level and also prints it to the console. The log levels available are 'info' and 'error'.

    Example usage:
        log_and_print('This is an info message', 'info')
        log_and_print('This is an error message', 'error')
    """
    print(message)
    if level == 'info':
        logging.info(message)
    elif level == 'error':
        logging.error(message)
