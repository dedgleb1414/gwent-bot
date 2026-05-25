content = open('index.py', encoding='utf-8').read()

old = '''async def start_turn(bot: Bot, gs: dict, game_id: str, side: str):
    """Send board + hand keyboard to the active player."""
    opp = get_opponent(side)
    player_id = gs["players"][side]["id"]
    opp_id = gs["players"][opp]["id"]

    board_pov = render_board(gs, side)
    board_opp = render_board(gs, opp)

    await bot.send_message(
        player_id,
        f"```\\n{board_pov}\\n```\\n\\n🃏 Выберите карту или спасуйте:",
        reply_markup=kb_hand(gs, side),
        parse_mode="Markdown"
    )
    await bot.send_message(
        opp_id,
        f"```\\n{board_opp}\\n```",
        parse_mode="Markdown"
    )'''

new = '''async def start_turn(bot: Bot, gs: dict, game_id: str, side: str):
    """Send or edit board message for both players."""
    opp = get_opponent(side)
    player_id = gs["players"][side]["id"]
    opp_id = gs["players"][opp]["id"]

    board_pov = render_board(gs, side)
    board_opp = render_board(gs, opp)

    # --- Active player ---
    text_active = f"```\\n{board_pov}\\n```\\n\\n🃏 Выберите карту или спасуйте:"
    msg_id_active = gs.get("msg_id", {}).get(side)
    if msg_id_active:
        try:
            await bot.edit_message_text(
                chat_id=player_id,
                message_id=msg_id_active,
                text=text_active,
                reply_markup=kb_hand(gs, side),
                parse_mode="Markdown"
            )
        except Exception:
            msg = await bot.send_message(
                player_id, text_active,
                reply_markup=kb_hand(gs, side),
                parse_mode="Markdown"
            )
            gs.setdefault("msg_id", {})[side] = msg.message_id
    else:
        msg = await bot.send_message(
            player_id, text_active,
            reply_markup=kb_hand(gs, side),
            parse_mode="Markdown"
        )
        gs.setdefault("msg_id", {})[side] = msg.message_id

    # --- Opponent ---
    if opp_id != AI_USER_ID:
        text_opp = f"```\\n{board_opp}\\n```"
        msg_id_opp = gs.get("msg_id", {}).get(opp)
        if msg_id_opp:
            try:
                await bot.edit_message_text(
                    chat_id=opp_id,
                    message_id=msg_id_opp,
                    text=text_opp,
                    parse_mode="Markdown"
                )
            except Exception:
                msg = await bot.send_message(
                    opp_id, text_opp,
                    parse_mode="Markdown"
                )
                gs.setdefault("msg_id", {})[opp] = msg.message_id
        else:
            msg = await bot.send_message(
                opp_id, text_opp,
                parse_mode="Markdown"
            )
            gs.setdefault("msg_id", {})[opp] = msg.message_id

    save_game(game_id, gs)'''

if old in content:
    open('index.py', 'w', encoding='utf-8').write(content.replace(old, new))
    print('Fixed')
else:
    print('NOT FOUND')