from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart
import asyncio
from database import is_user_subscribed, set_user_subscription
from config import TELEGRAM_BOT_TOKEN

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Клавиатура для главного меню
main_menu_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Меню кнопок', callback_data='menu')]
    ]
)

@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    text = (
        'Привет!\n\n'
        'Этот Бот предназначен для мониторинга открытия сделок и прочего в Крипто-Агенте.'
    )
    await message.answer(text, reply_markup=main_menu_kb)

# Хэндлер для меню кнопок
@dp.callback_query(lambda c: c.data == 'menu')
async def show_menu(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    subscribed = await is_user_subscribed(user_id)
    if subscribed:
        sub_text = 'Отписка'
        sub_callback = 'unsubscribe'
    else:
        sub_text = 'Подписка'
        sub_callback = 'subscribe'
    menu_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=sub_text, callback_data=sub_callback)]
        ]
    )
    await callback_query.message.edit_text('Меню кнопок:', reply_markup=menu_kb)

# Хэндлеры для подписки/отписки
@dp.callback_query(lambda c: c.data in ['subscribe', 'unsubscribe'])
async def handle_subscription(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if callback_query.data == 'subscribe':
        await set_user_subscription(user_id, True)
        text = 'Вы подписались!'
        next_btn = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text='Назад', callback_data='menu')]]
        )
    else:
        await set_user_subscription(user_id, False)
        text = 'Вы отписались. Будем ждать вас снова!'
        next_btn = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text='Назад', callback_data='menu')]]
        )
    await callback_query.message.edit_text(text, reply_markup=next_btn)

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    import asyncio
    async def main():
        # Установка команд бота
        await bot.set_my_commands([
            types.BotCommand(command='start', description='Запустить бота'),
            types.BotCommand(command='main_menu', description='Главное меню'),
        ])
        await dp.start_polling(bot)
    asyncio.run(main())
