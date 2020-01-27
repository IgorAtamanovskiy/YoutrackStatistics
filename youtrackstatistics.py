# coding: utf-8
import logging
import telebot
from telebot import apihelper
import json
import requests
from requests.exceptions import HTTPError
import pandas as pd
import sys

parameters = json.loads(open("config.json").read())

TELEGRAM_PROXY = parameters["preferences"]["tchat_proxy"]
TELEGRAM_TOKEN = parameters["preferences"]["tchat_token"]
TELEGRAM_PROTOCOL = parameters["preferences"]["tchat_protocol"]
TELEGRAM_CHATID = parameters["preferences"]["tchat_id"]

YOUTRACK_URL = parameters["preferences"]["youtrack_url"]
YOUTRACK_TOKEN = parameters["preferences"]["youtrack_token"]
YOUTRACK_PROJECT = parameters["preferences"]["youtrack_project"]

def main():
    try:
        if sys.argv[2] == "all":
            bugs_stat_res = GetBugsDynamics(sys.argv[1])
        elif sys.argv[2] == "closed":
            bugs_stat_res = GetClosedBugsStat(sys.argv[1])
        else:
            bugs_stat_res = GetBugsDynamics(sys.argv[1])

    except IndexError as e:
        try:
            bugs_stat_res = GetBugsDynamics(sys.argv[1])
        except IndexError as e:
            bugs_stat_res = GetBugsDynamics("week")

    logger = telebot.logger
    telebot.logger.setLevel(logging.DEBUG)

    apihelper.proxy = {TELEGRAM_PROTOCOL: TELEGRAM_PROXY}

    bot = telebot.TeleBot(TELEGRAM_TOKEN)

    # send message to chat
    bot.send_message(TELEGRAM_CHATID, bugs_stat_res[0], parse_mode="HTML")


def GetClosedBugsStat(date_period):
    arr_date_period = DatePeriod2Text(date_period)
    msg_text = arr_date_period[0]
    datetime_period = arr_date_period[1]

    # check closed issues
    closed_res = GetIssues(
        {"проект": YOUTRACK_PROJECT, "тип": "bug", "дата завершения": datetime_period}
    )
    str_closed_issues = closed_res[0]
    int_closed_total = closed_res[1]
    str_response_text = (
        "<b>Результаты работ по стаблизиации</b>\n\n"
        + msg_text
        + " было закрыто "
        + repr(int_closed_total)
        + " ошибок\n\n"
        "<b>Исправленные ошибки</b>\n" + str_closed_issues
    )

    result = [str_response_text, closed_res, int_closed_total]

    return result


def GetBugsDynamics(date_period):

    arr_date_period = DatePeriod2Text(date_period)
    msg_text = arr_date_period[0]
    datetime_period = arr_date_period[1]

    # check closed issues
    closed_res = GetIssues(
        {"проект": YOUTRACK_PROJECT, "тип": "bug", "дата завершения": datetime_period}
    )
    str_closed_issues = closed_res[0]
    int_closed_total = closed_res[1]

    # Check new issues
    new_res = GetIssues(
        {"проект": YOUTRACK_PROJECT, "тип": "bug", "создана": datetime_period}
    )

    str_new_issues = new_res[0]
    int_new_total = new_res[1]

    if (int_new_total - int_closed_total) > 0:
        str_dynam = "отрицательная (регистрируется больше, чем исправляется)"
    else:
        str_dynam = "положительная (исправляется больше, чем регистрируется)"

    str_response_text = (
        "<b>Результаты работ по стаблизиации</b>\n\n"
        + msg_text
        + " было закрыто "
        + repr(int_closed_total)
        + " ошибок и обнаружено "
        + repr(int_new_total)
        + " новых\n"
        "Динамика стабилизации "
        + str_dynam
        + "\n\n<b>Исправленные ошибки</b>\n"
        + str_closed_issues
        + "\n<b>Новые ошибки</b>\n"
        + str_new_issues
    )

    result = [str_response_text, new_res, int_new_total, closed_res, int_closed_total]

    return result


def DatePeriod2Text(date_period):
    msg_text = ""
    datetime_period = ""

    if date_period == "month":
        msg_text = "В этом месяце"
        datetime_period = "{В этом месяце}"
    elif date_period == "prevmonth":
        msg_text = "В прошлом месяце"
        datetime_period = "{В прошлом месяце}"
    elif date_period == "week":
        msg_text = "На этой неделе"
        datetime_period = "{на этой неделе}"
    elif date_period == "prevweek":
        msg_text = "На прошлой неделе"
        datetime_period = "{На прошлой неделе}"
    elif date_period == "day":
        msg_text = "Сегодня"
        datetime_period = "сегодня"
    else:
        msg_text = "Сегодня"
        datetime_period = "сегодня"

    return [msg_text, datetime_period]


def GetIssues(filter):
    try:
        str_filter = ""
        for key in filter.keys():
            str_filter = str_filter + key + ":" + filter[key] + "%20"
        str_filter.replace(" ", "%20")

        str_filter = str_filter + "сортировать:%20Приоритет%20по%20возр.%20&max=1000"

        url = YOUTRACK_URL + "issue/?filter=" + str_filter
        headersParams = {
            "Authorization": "Bearer " + YOUTRACK_TOKEN,
            "Accept": "Application/json",
        }
        response = requests.get(url, headers=headersParams)

        items = json.loads(response.text)

        issues = items["issue"]

        id = []
        numberInProject = []
        summary = []
        priority = []

        for i in range(len(issues)):

            fields = issues[i]["field"]

            id.append(issues[i]["id"])

            j = 0
            fieldsCounter = 0

            for j in range(len(fields)):
                if fields[j]["name"] == "numberInProject":
                    numberInProject.append(fields[j]["value"])
                    fieldsCounter += 1
                elif fields[j]["name"] == "summary":
                    summary.append(fields[j]["value"])
                    fieldsCounter += 1
                elif fields[j]["name"] == "Priority":
                    priority.append(fields[j]["value"])
                    fieldsCounter += 1
                else:
                    if fieldsCounter == 3:
                        break

        dictIssues = {
            "id": id,
            "numberInProject": numberInProject,
            "summary": summary,
            "priority": priority,
        }
        dfIssues = pd.DataFrame(dictIssues)

        response.raise_for_status()

    except HTTPError as http_err:
        print("HTTP error occurred: " + http_err)
    except Exception as err:
        print("Other error occurred: " + err)
    else:
        return ItemsDataFrame2List(dfIssues, filter)


def ItemsDataFrame2List(dfitems, filterinfo):
    df_closed_issues = dfitems
    int_closed_total = len(df_closed_issues)

    str_closed_issues = ""
    if int_closed_total <= 10:
        for index, row in df_closed_issues.iterrows():
            str_closed_issues = (
                str_closed_issues
                + "<b>"
                + repr(row["id"])
                + "</b>"
                + " "
                + repr(row["summary"])
                + " "
                + repr(row["priority"])
                + "\n"
            )
    else:
        counter = 0
        for index, row in df_closed_issues.iterrows():
            if counter < 10:
                str_closed_issues = (
                    str_closed_issues
                    + "<b>"
                    + repr(row["id"])
                    + "</b>"
                    + " "
                    + repr(row["summary"])
                    + " "
                    + repr(row["priority"])
                    + "\n"
                )
                counter += 1
            else:
                break

        str_closed_issues = (
            "<b>Первые 10</b>\n"
            + str_closed_issues
            + "\nВоспользуйтесь ссылкой для полного списка https://youtrack.onelya.ru/issues/"
            + list(filterinfo.values())[0]
            + "?q="
            + str(list(filterinfo.keys())[1]).replace(" ", "%20")
            + ":"
            + list(filterinfo.values())[1]
            + "%20"
            + str(list(filterinfo.keys())[2]).replace(" ", "%20")
            + ":"
            + str(list(filterinfo.values())[2]).replace(" ", "%20")
            + "сортировать:%20Приоритет%20по%20возр.%20"
            + "\n"
        )

    result = [str_closed_issues, int_closed_total, df_closed_issues]
    return result

if __name__ == "__main__":
    main()