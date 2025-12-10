import asyncio
from asyncio import set_event_loop, new_event_loop, get_event_loop

from typing import List

from telethon import TelegramClient, errors, functions, types, events
from telethon.errors.rpcbaseerrors import BadRequestError
from telethon.tl.types import InputPeerChannel






API_ID = 123
API_HASH = "123"

client = TelegramClient("account", api_id=API_ID, api_hash=API_HASH)
client.start()





# Получение ссылки на подарок
def key_of(gift: types.TypeStarGift) -> str:
    return f'https://t.me/nft/{gift.slug}' if getattr(gift, 'slug', None) else f'id:{gift.id}'





# Получение подарков с профиля аккаунта
async def get_self_gifts(client: TelegramClient) -> List[types.StarGiftUnique]:
    saved: types.payments.SavedStarGifts = await client(
        functions.payments.GetSavedStarGiftsRequest(peer=types.InputPeerSelf(),
                                                    offset='', limit=1000))
    gifts = [g for g in saved.gifts
             if isinstance(g.gift, types.StarGiftUnique)]
    
    return gifts





# Отправка подарка
async def send_gift(client: TelegramClient, gift_object: types.SavedStarGift, destination_id: types.TypeInputPeer):
    k = key_of(gift_object)

    invoice = None

    if gift_object.msg_id:
        invoice = types.InputInvoiceStarGiftTransfer(
        stargift=types.InputSavedStarGiftUser(msg_id=gift_object.msg_id),
        to_id=destination_id
    )
    else:
        channel = await client.get_entity(gift_object.gift.owner_id.channel_id)
        channel_peer = InputPeerChannel(channel_id=channel.id, access_hash=channel.access_hash)

        invoice = types.InputInvoiceStarGiftTransfer(
        stargift=types.InputSavedStarGiftChat(peer=channel_peer, saved_id=gift_object.saved_id),
        to_id=destination_id
    )
    
    try:
        form = await client(functions.payments.GetPaymentFormRequest(invoice=invoice))
        price = sum(p.amount for p in form.invoice.prices)   # Stars
        if price == 0:
            # иногда Telegram всё-таки шлёт 0 → безопаснее прямой трансфер
            raise BadRequestError(400, 'NO_PAYMENT_NEEDED', None)
        await client(functions.payments.SendStarsFormRequest(
            form_id=form.form_id, invoice=invoice))
        return "SUCCESS"

    except BadRequestError as e:
        print(e.message)

        if "BALANCE_TOO_LOW" in e.message:
            return "BALANCE_TOO_LOW"
        elif e.message == 'NO_PAYMENT_NEEDED':
            # бесплатный перевод
            try:
                await client(functions.payments.TransferStarGiftRequest(
                    stargift=types.InputSavedStarGiftUser(msg_id=gift_object.msg_id),
                    to_id=destination_id
                ))
                return "SUCCESS"
            except BadRequestError as e2:
                if e2.message in {'STARGIFT_NOT_UNIQUE', 'STARGIFT_USAGE_LIMITED'}:
                    print(f'⏩ Skip {k} ({e2.message})')
                else:
                    print(e2.message)
        elif e.message in {'STARGIFT_NOT_UNIQUE', 'STARGIFT_USAGE_LIMITED'}:
            print(f'⏩ Skip {k} ({e.message})')
        else:
            print('raise')







# async def main1():
#     gifts = await get_self_gifts(client)
#     for gift in gifts:
#         destination = await client.get_input_entity("by_Unix")
#         await send_gift(client, gift, destination)

# loop = get_event_loop()
# loop.run_until_complete(main1())



# Хендлер для получения всех входящих УНИКАЛЬНЫХ (NFT) подарков
@client.on(events.Raw())
async def handler(event):
    if isinstance(event, types.UpdateNewMessage):
        if isinstance(event.message, types.MessageService):
            if isinstance(event.message.action, types.MessageActionStarGiftUnique):
                gift = event.message.action.gift
                print(gift) # Вывести всю сырую информацию о гифте
                print("New gift from:", event.message.peer_id.user_id)
                print("  Gift ID:", gift.gift_id)
                print("  Gift Name:", gift.slug)
                print("  Attributes:")
                print("    Model:", gift.attributes[0].name)
                print("    Backdrop:", gift.attributes[2].name)
                print("    Symbol:", gift.attributes[1].name)
            


client.run_until_disconnected()