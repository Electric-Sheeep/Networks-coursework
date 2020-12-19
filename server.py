import socket, select

local_ip = '127.0.0.1'
port = 2222


header_size = 30
ttype_lookup = {'/all':0, '/whisper':1, '/newname':2, '/quit':3, '/users':4}

type_display = ['TO-ALL:', 'WHISPER:', 'CHANGE NAME REQUEST:', "REQUESTING TO QUIT", "REQUESTS LIST OF USERS"]
command_prefixes = ['/all', '/whisper', '/newname', '/quit', '/users']

class Server_err(Exception):
    pass
class UserDisconnectErr(Exception):
    pass

def rev_dict_lookup(dict, seach_val):
    for key, val in dict:
        if val == seach_val:
            return val
    return False

def constuctMessage(message, type, sender):
    return (f'{len(message):<10}' + f'{type:<10}' + f'{sender:<10}' + message).encode()

def receiveMessage(socket):
    sum_message = ''
    fresh = True
    take_in = header_size


    while True:
        try:
            part = (socket.recv(take_in)).decode()
        except:
            return False, False, False
        if fresh:
            take_in = int(part[0:9])
            message_type = int(part[10:19])
            sender = part[20:]
            fresh = False
        else:
            sum_message += part

        if not(len(sum_message) < take_in):
            if len(sum_message) != take_in:
                raise Server_err("oversized Msg received")
            return message_type, sender, sum_message




def send_message(recipients, msg, type, sender, out_socket):
    msg = sender + ': ' + msg
    for recipient in recipients:
        recipient.sendall(constuctMessage(msg, type, sender))




class room():
    def __init__(self, port):
        self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_socket.bind((local_ip, port))
        self.listen_socket.listen()


        self.room_socket = self.listen_socket

        self.all_socket_list = [self.listen_socket]

        self.client_username = {}

        self.client_return_addr = {}


    def recipientsViaType(self, message_type, all_posible_recipients,sender, message_data=None ):
        """
        type_lookup = {'/all':0, '/whisper':1, '/newname':2, '/quit':3, '/users':4}
        :param message_type:
        :param all_posible_recipients:
        :param message_data:
        :return:
        """

        try:
            sender = self.client_username[sender]
        except:
            sender = False

        # to all
        if message_type == 0 or message_type == 2 or message_type == 3:
            return all_posible_recipients

        # to one whisperUser
        elif message_type == 1:
            if sender:
                #reverse dict lookup
                all_posible_recipients = [rev_dict_lookup(self.client_username, message_data.split(" ")[0])]

                if not(all_posible_recipients[0]):
                    return all_posible_recipients
            else:
                return False

        else:
            return False

        if message_type == 4:
            return [sender]

    def commandHandler(self, All_posibles_recipients, sender_socket, whole_msg, message_type):
        """
            command_prefixes = ['/all', '/whisper', '/newname', '/quit', '/users']

            messages will come in with form '/command other-args'
            splits msg up into each of these parts

            first argumsnt will deffine main direction for command, what will then dictate how rest of
            arguments used
            :param recipients:
            :param msg:
            :param type:
            :param sender:
            :return:
        """
        try:
            arguments = whole_msg.split(" ")
        except Exception as e:
            raise UserDisconnectErr(f"error receiving message from: {sender_socket}") from e
            pass


        # if mesage not a command, sends to the recipients. handles messages to all and recipients
        if message_type == 0  :
            send_message(All_posibles_recipients, whole_msg, 0, self.client_username[sender_socket], self.room_socket)


        elif message_type == 1 :
            send_message(All_posibles_recipients, whole_msg, 0, self.client_username[sender_socket], self.room_socket)



        # change nickname to second arg, inform everyone
        elif message_type == 2:
            newname = arguments[1]

            msg = f"User {self.client_username[sender_socket].copy()} is now {newname}"
            self.client_username[sender_socket] = newname

            send_message(All_posibles_recipients, msg, 0, 'SERVER', self.room_socket)

        #client does a controlled quit. all other users notified and client removed from all server lists
        elif message_type == 4:
            msg = f"user {self.client_username[sender_socket]} disconnected"

            self.all_socket_list.remove(sender_socket)
            del self.client_username[sender_socket]

            send_message(All_posibles_recipients, msg, 0, 'SERVER', self.room_socket)

        #sends list of surrent users to client 
        elif message_type == 5:
            send_message([sender_socket], self.client_username, 0, 'SERVER', self.room_socket)




    def monitorRoom(self):
        while True:
            r_sockets, w_sockets, e_sockets = select.select(self.all_socket_list, [], self.all_socket_list,1)


            for current_socket in r_sockets:
                if current_socket == self.room_socket:
                    disconnect = False

                    #accepts the new connection reqest
                    cli_socket, cli_addr = current_socket.accept()
                    current_socket = cli_socket

                    #brings in the message form the initial request
                    try:
                        message_type,message_sender, message_data = receiveMessage(cli_socket)

                        self.client_username[cli_socket] = message_data
                        self.all_socket_list.append(cli_socket)
                        self.client_return_addr[cli_socket] = message_sender

                        #send_message([cli_socket], f'WELCOME to the server {message_data}', 0, "server", self.room_socket)


                        print(f"new connection from {message_data} @ {cli_addr}")
                        message_data = f"new connection from {message_data}"



                    except Exception as e:
                        raise Server_err(f"error receiving message from: {cli_socket}") from e






                else:
                    try:
                        message_type,message_sender, message_data = receiveMessage(current_socket)

                    except UserDisconnectErr as e:
                        message_data = f"user {self.client_username[current_socket]} disconnected"
                        message_type = 3
                        quiting_user = self.client_username[current_socket]

                        self.all_socket_list.remove(current_socket)
                        del self.client_username[current_socket]
                        raise UserDisconnectErr(f"user {self.client_username[current_socket]} disconnected") from e

                        disconnect = True



                    #otherwise the received message is valid and gets printed to server screen

                    if not(disconnect):
                        print(f"{self.client_username[current_socket]}:{type_display[int(message_type)]}>  {message_data}")


                #finds clients to send result of received msg to
                recipients = self.recipientsViaType(message_type, [recipient for recipient in self.all_socket_list if recipient != self.room_socket],current_socket, message_data)


                self.commandHandler(recipients, current_socket, message_data, message_type)




if __name__ == '__main__':
    room1 = room(port)
    room1.monitorRoom()




