"""
Запуск всего через этот файл
"""

import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

from complete_bot import *

async def main():
    print("🔧 Инициализация базы данных...")
    init_database()

    print("🤖 Создание бота...")
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))

    application.add_handler(CommandHandler("schedule", my_schedule))
    application.add_handler(CommandHandler("thisweek", this_week_schedule))
    application.add_handler(CommandHandler("homework", my_homework))
    application.add_handler(CommandHandler("info", my_info))
    application.add_handler(CommandHandler("payment", my_payment))

    application.add_handler(CommandHandler("requests", view_requests))
    application.add_handler(CommandHandler("accept", accept_request))
    application.add_handler(CommandHandler("reject", reject_request))
    application.add_handler(CommandHandler("students", list_students))
    application.add_handler(CommandHandler("remove", remove_student))
    application.add_handler(CommandHandler("setnickname", set_nickname))

    application.add_handler(CommandHandler("addschedule", add_schedule))
    application.add_handler(CommandHandler("removeschedule", remove_schedule))
    application.add_handler(CommandHandler("reschedule", reschedule_lesson))

    application.add_handler(CommandHandler("addhw", add_homework))
    application.add_handler(CommandHandler("deletehw", delete_homework))
    application.add_handler(CommandHandler("setsubject", set_subject))

    application.add_handler(CommandHandler("setrate", set_rate))
    application.add_handler(CommandHandler("setduration", set_duration))
    application.add_handler(CommandHandler("addpayment", add_payment))
    application.add_handler(CommandHandler("clearpayment", clear_payment))

    application.add_handler(CommandHandler("announce", announce))

    await application.initialize()
    await application.start()

    print("⏰ Настройка планировщика...")
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Almaty'))
    scheduler.add_job(send_lesson_reminders, 'cron', hour=3, minute=0, args=[application])
    scheduler.add_job(send_payment_reminders, 'cron', hour=10, minute=0, args=[application])
    scheduler.add_job(update_remaining_lessons, 'cron', hour=23, minute=0, args=[application])
    scheduler.start()

    print("✅ Планировщик запущен")
    print("🚀 Бот запущен!")
    print(f"👨‍💼 Admin ID: {ADMIN_ID}")
    print("📱 Бот готов к работе...")

    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
