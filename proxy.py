from fastapi import FastAPI, Response, Request, WebSocket, WebSocketDisconnect, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
import time
from async_poe_client import Poe_Client
import asyncio
import sys
import time
import json
import atexit
import uvicorn

app = FastAPI()


def jsonToText(message):
    result = []
    current_chunk = ""
    max_length = 4000
    
    for message in message['messages']:
        if message['role'] == "assistant" : message['role'] = config['replace']['assistant']
        if message['role'] == "user" : message['role'] = config['replace']['user']
        if message['role'] == "system" : message['role'] = config['replace']['system']
        msg = f"{message['role']}: {message['content']}\n\n"
        if len(current_chunk) + len(msg) <= max_length:
            current_chunk += msg
        else:
            result.append(current_chunk)
            current_chunk = msg
    
    if current_chunk:  # Si quedó algún trozo sin agregar
        result.append(current_chunk)

    return result

async def main():
  async with websockets.serve(websocket_handler, "localhost", 8765):
    await asyncio.Future()

@app.post('//chat/completions')
@app.post('/chat/completions')
async def completions(request: Request):
    response = ""
    # Obtener el mensaje de la solicitud y partimos el prompt cada 4000 caracteres para que poe lo pueda procesar bien
    messages = jsonToText(await request.json())
    stream = (await request.json())['stream']

    if stream:
        #response = JSONResponse(content=event_stream(messages))
        #response.headers["Content-Type"] = "text/event-stream"
        #return event_stream(messages)

        #STREAMING DE MENSAJES
        async def event_stream():
            response = {
                "choices": [{
                    "delta": {
                        "role":"assistant",
                    }
                }]
            }
            yield '\n\ndata: ' + json.dumps(response)
            time.sleep(0.1)
            prev_chunk = ""

            for i in range(len(messages)):
                message = messages[i]
                response = {"choices": [{"delta": {"content": ""}}]}
                if i == len(messages) - 1:
                    async for chunk in cliente.ask_stream(url_botname=config['settings']['bot'], question=message, suggest_able=False):
                        if aborted: #si le dan al boton stop, borramos el ultimo mensaje para cancelar la generacion (WIP)
                            print ("Mensaje cancelado")
                            await cliente.delete_bot_conversation(url_botname=config['settings']['bot'], count=1)
                            handle_abort(False)
                            break

                        temp_chunk = prev_chunk + chunk

                        if ("A:" in temp_chunk) or ("U:" in temp_chunk) or ("S:" in temp_chunk): #evitamos enviar el A: que representa el inicio de mensajes de asistente.
                            response["choices"][0]["delta"]["content"] = temp_chunk.replace("A:","").replace("U:", "").replace("S:","")
                            yield '\n\ndata: ' + json.dumps(response)
                            chunk = ""
                        else:
                            response["choices"][0]["delta"]["content"] = prev_chunk
                            yield '\n\ndata: ' + json.dumps(response)

                        if ("U:" in temp_chunk) : #esta intentando crear mensajes por nosotros, asi que cancelamos la generacion borrando el ultimo mensaje, y salimos del for
                            await cliente.delete_bot_conversation(url_botname=config['settings']['bot'], count=1)
                            prev_chunk = ""
                            break

                        prev_chunk = chunk
                    response["choices"][0]["delta"]["content"] = prev_chunk
                    yield '\n\ndata: ' + json.dumps(response)
                    time.sleep(0.2)
                    yield '\n\ndata: [DONE]'
                else: 
                    #estos son los primeros mensajes, se borran apenas se generan respuesta
                    async for chunk in cliente.ask_stream(url_botname=config['settings']['bot'], question=message, suggest_able=False):
                        await cliente.delete_bot_conversation(url_botname=config['settings']['bot'], count=1)
                        break
        return EventSourceResponse(event_stream())
    # NO STREAMING
    for i in range(len(messages)):
        message = messages[i]

        if i == len(messages) - 1:
            chunk = await cliente.ask(url_botname=config['settings']['bot'], question=message, suggest_able=False)
            chunk = chunk.split("U:")[0].replace("A:","")
            response = {
                "choices": [
                    {
                    "message": {
                        "role":"assistant",
                        "content": chunk
                    }
                    }
                ] 
            }
        else: 
            #estos son los primeros mensajes, se borran apenas se generan respuesta
            async for chunk in cliente.ask_stream(url_botname=config['settings']['bot'], question=message, suggest_able=False):
                await cliente.delete_bot_conversation(url_botname=config['settings']['bot'], count=1)
                break

        #print(message)

    return JSONResponse(content=response)

def handle_abort(status = True):
    global aborted
    aborted = status

async def process_chunks(message):
    async for chunk in cliente.ask_stream(url_botname=config['settings']['bot'], question=message, suggest_able=False):
        if aborted:
            print("Mensaje cancelado")
            await cliente.delete_bot_conversation(url_botname=config['settings']['bot'], count=1)
            handle_abort(False)
            break

@app.route('/models', methods=['GET'])
@app.route('//models', methods=['GET'])
def models(request: Request):
    response = {
        "object": "list",
        "data": [
            {
                "id": "gpt-3.5",
                "object": "model",
                "created": time.time(), 
                "owned_by": "openai",
                "permission": [],
                "root": "gpt-3.5",
                "parent": None
            }
        ]
    }
    
    return JSONResponse(content=response)


async def init_poe():
    global cliente
    cliente = await Poe_Client(token, formkey).create()

    bots = await cliente.get_available_bots()
    print("Esta es tu lista de bots:\n")
    for bbot in bots:
        print(bbot['handle'])
    print("\nSi cambias al bot tienes que reiniciar esta celda para que el cambio surja efecto")

    print("\nTodo listo, Ya puedes conectarte a ST!\n")

async def main():
    global token, formkey, bot, config
    config=[]
    config_path = "config.json"

    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    if len(sys.argv) > 1:
        config['settings']['token'] = sys.argv[1]

    if len(sys.argv) > 2:
        config['settings']['bot'] = sys.argv[2]

    if len(sys.argv) > 3:
        config['settings']['formkey'] = sys.argv[3]
        
        with open(config_path, 'w') as config_file:
            json.dump(config, config_file)

    token = config['settings']['token']
    formkey = config['settings']['formkey']
    bot = config['settings']['bot']

    await init_poe()

@app.on_event("shutdown")
def shutdown_event():
    # Implementa lo que necesites hacer al detener el servidor FastAPI
    pass

if __name__ == '__main__':
    asyncio.run(main())
    uvicorn.run(app, host="0.0.0.0", port=5000)