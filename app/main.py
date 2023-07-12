import logging

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.utils import executor

from models import Session, User, Order, Product

# Bot token can be obtained via https://t.me/BotFahter
TOKEN = "6121790823:AAFnFqf0W2egMndELkcZYAJ9Xq98u22L3rU"

bot = Bot(TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


class Form(StatesGroup):
    name = State()  # Will be represented in storage as 'Form:name'
    phone = State()  # Will be represented in storage as 'Form:number'
    email = State()  # Will be represented in storage as 'Form:email'


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    """
    Conversation's entry point
    """
    # Set state
    await Form.name.set()
    await bot.send_message(
        text="""
Для оформления заказа необходимо:
1)Зарегистрироваться по ФИО/номеру телефона/почте
2)Отправить ссылку на тот товар, который желаете купить
3)Подтвердить заказ
        
Для регистрации введите ФИО""",
        chat_id=message.chat.id
    )


@dp.message_handler(state=Form.name)
async def process_full_name(message: types.Message, state: FSMContext):
    """
    Process full name
    """
    async with state.proxy() as data:
        data['name'] = message.text

    # Update state and data
    await Form.next()
    await message.reply("Введите номер телефона")


@dp.message_handler(state=Form.phone)
async def process_phone_number(message: types.Message, state: FSMContext):
    """
    Process phone number
    """
    async with state.proxy() as data:
        data['phone'] = message.text

    # Update state and data
    await Form.next()
    await message.reply("Введите email")


@dp.message_handler(state=Form.email)
async def process_email(message: types.Message, state: FSMContext):
    """
    Process email
    """
    async with state.proxy() as data:
        data['email'] = message.text

        # Update state and data
        await Form.next()
        session = Session()
        session.query(User).filter(User.id == message.chat.id).delete()
        session.commit()
        new_user = User(id=message.chat.id, **data)
        session.add(new_user)
        session.commit()
        session.close()
        kb = [
            [types.KeyboardButton(text="Новый заказ")],
        ]
        keyboard = types.ReplyKeyboardMarkup(keyboard=kb)
        await bot.send_message(
            text="Вы успешно зарегистрированы\nИмя: {name}\nТелефон: {phone}\nEmail: {email}".format(**data),
            chat_id=message.chat.id,
            reply_markup=keyboard
        )
        # And remove current user data from storage
        await state.finish()


class OrderCreation(StatesGroup):
    waiting_for_products = State()
    waiting_for_address = State()
    waiting_confirmation = State()


@dp.message_handler(Text(equals="Новый заказ"))
async def new_order(message: types.Message):
    await OrderCreation.waiting_for_products.set()
    await message.reply("Введите ссылки на товары через пробел", reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(state=OrderCreation.waiting_for_products)
async def process_products(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['products'] = message.text.split()

    await OrderCreation.next()
    await message.reply("Введите адрес доставки")


@dp.message_handler(state=OrderCreation.waiting_for_address)
async def process_address(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['address'] = message.text

        products = '\n'.join(data['products'])

        await OrderCreation.next()
        await message.reply(
            f"Подтвердите заказ:\n"
            f"Товары:\n{products}\n"
            f"Адрес доставки: {data['address']}\n"
            f"Нажмите /confirm для подтверждения\n"
            f"Нажмите /cancel для отмены"
        )


@dp.message_handler(state=OrderCreation.waiting_confirmation)
async def process_confirmation(message: types.Message, state: FSMContext):
    kb = [
        [types.KeyboardButton(text="Новый заказ")],
        [types.KeyboardButton(text="Мои заказы")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb)
    if message.text == '/confirm':
        async with state.proxy() as data:

            try:
                with Session() as session:
                    user = session.query(User).filter(User.id == message.chat.id).first()
                    session.expunge(user)
                    if user:
                        order = Order(user_id=user.id, address=data['address'])
                        session.add(order)
                        session.flush()  # commit not needed yet, just flushing changes to db to get order.id
                        for product in data['products']:
                            session.add(Product(order_id=order.id, link=product))
                        session.commit()  # commit transaction
            except Exception as e:
                print(f"Error occurred: {e}")
                session.rollback()  # rollback transaction if an error occurred, to undo changes
            finally:
                session.close()

            products = '\n'.join(data['products'])
            await message.reply(f"Заказ оформлен\n"
                                f"Товары:\n{products}\n"
                                f"Адрес доставки: {data['address']}\n"
                                f"Имя: {user.name}\n"
                                f"Телефон: {user.phone}\n"
                                f"Email: {user.email}\n"
                                f"Статус: Модерация\n"
                                f"Итоговая цена: Будет рассчитана после модерации\n",
                                reply_markup=keyboard
                                )

            await state.finish()

    elif message.text == '/cancel':
        await message.reply(f"Заказ отменен", reply_markup=keyboard)
        await state.finish()


@dp.message_handler(Text(equals="Мои заказы"))
async def my_orders(message: types.Message):
    session = Session()
    user = session.query(User).filter(User.id == message.chat.id).first()
    session.expunge(user)
    if user:
        orders = session.query(Order).filter(Order.user_id == user.id).all()
        for order in orders:
            session.expunge(order)
            products = session.query(Product).filter(Product.order_id == order.id).all()
            products = '\n'.join([product.link for product in products])
            await bot.send_message(text=f"Заказ №{order.id}\n"
                                        f"Товары:\n{products}\n"
                                        f"Адрес доставки: {order.address}\n"
                                        f"Имя: {user.name}\n"
                                        f"Телефон: {user.phone}\n"
                                        f"Email: {user.email}\n"
                                        f"Статус: Модерация\n"
                                        f"Итоговая цена: Будет рассчитана после модерации\n",
                                   chat_id=message.chat.id)


def main():
    executor.start_polling(dp)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
