from enum import Enum
import textwrap

from colorama import init as colorama_init
from colorama import Fore
from colorama import Style

colorama_init()


class UserTypeColor(Enum):
    """
    Enumerate user type color
    """

    USER = f"{Fore.BLUE}"
    INVOICE_DATA_ENGINEER = f"{Fore.CYAN}"
    INVOICE_UPDATE_DATA_ENGINEER = f"{Fore.LIGHTCYAN_EX}"
    FINANCE_CLERK = f"{Fore.LIGHTYELLOW_EX}"
    RECONCILIATION_AGENT = f"{Fore.GREEN}"
    EMAIL_DATA_ENGINEER = f"{Fore.YELLOW}"
    TOOL = f"{Fore.LIGHTRED_EX}"


class BeautifiedLogging:
    """
    Standard logging
    """

    standard_divider = "========================================================="
    end_style = f"{standard_divider}{Style.RESET_ALL}"

    def __print_str(self, colorization: str, title: str, msg: str):
        dedent_msg = textwrap.dedent(
            f"""
        {title}
                                    
        {msg}
        """
        )
        print(f"{colorization}{self.standard_divider}\n{dedent_msg}\n{self.end_style}")

    def info(self, user_type: str, msg: str):
        """Color matcher"""
        colorization = ""

        match user_type:
            case "User":
                colorization = UserTypeColor.USER.value
            case "Invoice_Data_Engineer":
                colorization = UserTypeColor.INVOICE_DATA_ENGINEER.value
            case "Invoice_Update_Data_Engineer":
                colorization = UserTypeColor.INVOICE_UPDATE_DATA_ENGINEER.value
            case "Reconciliation_agent":
                colorization = UserTypeColor.RECONCILIATION_AGENT.value
            case "Email_Data_Engineer":
                colorization = UserTypeColor.EMAIL_DATA_ENGINEER.value
            case "Finance_Clerk":
                colorization = UserTypeColor.TOOL.value
            case "Tool":
                colorization = UserTypeColor.TOOL.value
            case _:
                colorization = UserTypeColor.USER.value

        user_type = user_type.replace("_", " ")
        self.__print_str(colorization=colorization, title=f"{user_type}:", msg=msg)
        return

    def debug(self, title: str, msg: str):
        """
        Debug logs
        """
        self.__print_str(colorization=f"{Fore.YELLOW}", title=title, msg=msg)
        return

    def success(self, title: str, msg: str):
        """
        Success logs
        """
        self.__print_str(colorization=f"{Fore.GREEN}", title=title, msg=msg)
        return

    def error(self, title: str, msg: str):
        """
        Error logs
        """
        self.__print_str(colorization=f"{Fore.RED}", title=title, msg=msg)
        return


if __name__ == "__main__":
    log = BeautifiedLogging()
    log.info(user_type="EMAIL_DATA_ENGINEER", msg="Hi")
