#!/usr/bin/env python

import json
from flask import Flask, render_template, redirect, url_for, request, send_from_directory, session
from flask_mysqldb import MySQL
import hashlib
from base64 import b64encode
from flask import jsonify
from flask_socketio import SocketIO, send, emit
from datetime import datetime

SESSION_TYPE = 'memcache'

app = Flask(__name__)
app.secret_key = 'ourSpace'
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'toor'
app.config['MYSQL_DB'] = 'myspace'
mysql = MySQL(app)


# create table login_credentials(
#     email varchar(50) primary key not null,
#     password varchar(32) not null
# );
# create table user_profile(
#     email varchar(50) primary key not null references login_credentails(email),
#     username varchar(50) not null,
#     gender varchar(10) not null,
#     dob varchar(10) not null,
#     photo mediumblob
# );
# create table friend_list(
#     email1 varchar(50) not null references login_credentials(email),
#     email2 varchar(50) not null references login_credentials(email),
#     constraint pk_constraint primary key(email1, email2)
# );
# create table friend_request(
#     email1 varchar(50) not null references login_credentials(email),
#     email2 varchar(50) not null references login_credentials(email),
#     constraint pk_constraint primary key(email1, email2)
# );
# create table post(
#     email varchar(50) not null references login_credentials(email),
#     post_id int not null,
#     image mediumblob,
#     text varchar(1000) not null, #### either image or text has to be not null, or just make text as not null?
#     timestamp bigint not null,
#     likes int not null,
#     constraint pk_constraint primary key(email, post_id)
# );
# create table likes(
#     poster_email varchar(50) not null references login_credentials(email),
#     post_id int not null references post(post_id),
#     liker_email varchar(50) not null references login_credentials(email),
#     constraint pk_constraint primary key(poster_email, post_id, liker_email)
# );
# create table chat(
#     email1 varchar(50) not null references login_credentials(email),
#     email2 varchar(50) not null references login_credentials(email),
#     message varchar(2000) not null, #### need to handle empty messages
#     timestamp bigint not null
# );
# create table admin_credentials(
#     email varchar(50) primary key not null,
#     password varchar(32) not null
# );
# create table phone_numbers(
#     email varchar(50),
#     phone_no varchar(12),
#     constraint pk_constraint primary key(email, phone_no)
# );
# create table schools(
#     email varchar(50),
#     school varchar(30),
#     constraint pk_constraint primary key(email, school)
# );
#
# delimiter $$
# create procedure get_unix_timestamp()
# begin
#     select unix_timestamp();
# end $$
# delimiter ;


socketio = SocketIO(app)
users = {}


@app.route('/')
def identify():
    return render_template('identify.html')


@app.route('/check_user', methods=['GET', 'POST'])
def check_user():
    email = request.form['email']
    cur = mysql.connection.cursor()
    cur.execute('select * from login_credentials where email=%s', [email])
    result = cur.fetchall()
    cur.close()
    if len(result) != 0:
        return render_template('login.html', email=email)
    return render_template('signup.html', email=email)


@app.route('/signup')
def signup():
    return render_template('signup.html')


@app.route('/register_user', methods=['GET', 'POST'])
def register_user():
    if request.method == 'POST':
        school = []
        school_ctr = 0
        while True:
            if 'school' + str(school_ctr) in request.form:
                school.append(request.form['school' + str(school_ctr)])
                school_ctr = school_ctr + 1
            else:
                break
        phone = []
        phone_ctr = 0
        while True:
            if 'phone_no' + str(phone_ctr) in request.form:
                phone.append(request.form['phone_no' + str(phone_ctr)])
                phone_ctr = phone_ctr + 1
            else:
                break

        email = request.form['email']
        password = request.form['pass']
        passwordhash = hashlib.md5(password.encode()).hexdigest()
        username = request.form['username']
        uploadedImage = request.files['profilePhoto']
        gender = request.form['gender']
        dob = request.form['dob']
        imageBytes = uploadedImage.read()

        cur = mysql.connection.cursor()
        try:
            cur.execute('insert into login_credentials values(%s, %s)',
                        [email, passwordhash])
            mysql.connection.commit()
        except:
            print("in except")
            return '<script>alert("Email already exists");window.location=\'/signup\'</script>'

        if imageBytes != '':  # needs to be checked
            image = b64encode(imageBytes).decode('utf-8')
            cur.execute('insert into user_profile values(%s, %s, %s, %s, %s)', [
                        email, username, gender, dob, image])  # obj or image?
            mysql.connection.commit()

        for item in school:
            cur.execute('insert into schools values(%s, %s)', [email, item])
            mysql.connection.commit()
        for item in phone:
            cur.execute('insert into phone_numbers values(%s, %s)',
                        [email, item])
            mysql.connection.commit()

        cur.close()
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    return render_template('login1.html')


@app.route('/verify_user', methods=['GET', 'POST'])
def verify_user():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['pass']
        passwordhash = hashlib.md5(password.encode()).hexdigest()
        cur = mysql.connection.cursor()
        cur.execute('select * from login_credentials where email=%s', [email])
        result = cur.fetchall()  # fetch all entries which satisfied the query
        cur.close()
        dbpassword = result[0][1]
        if passwordhash == dbpassword:
            session['email'] = email
            return redirect(url_for('news_feed'))
        else:  
            return render_template('login.html', email=email)
    return


@app.route('/myProfile')
def myProfile():
    email = session['email']
    cur = mysql.connection.cursor()
    cur.execute(
        'select photo, username, gender, dob from user_profile where email=%s', [email])
    result = cur.fetchall()
    posts = []
    cur.execute(
        'select username, image, text, likes, email, post_id,timestamp from post natural join user_profile where email = %s order by timestamp', [email])
    results = cur.fetchall()
    for post in results:
        temp_post = {}
        temp_post['username'] = post[0]
        temp_post['image'] = post[1].decode('utf-8')
        temp_post['text'] = post[2]
        temp_post['likes'] = post[3]
        temp_post['email'] = post[4]
        temp_post['post_id'] = post[5]
        temp_post['timestamp'] = datetime.fromtimestamp(
            post[6]).strftime('%d-%m-%Y %H:%M')

        posts.append(temp_post)

    phone = []
    cur.execute('select phone_no from phone_numbers where email=%s', [email])
    results = cur.fetchall()
    print(results)
    for item in results:

        phone.append(item[0])
    school = []
    cur.execute('select school from schools where email=%s', [email])
    results = cur.fetchall()
    for item in results:
        school.append(item[0])

    cur.close()

    image = result[0][0].decode("utf-8")
    return render_template('myProfile.html', posts=posts, email=email, image=image, username=result[0][1], phone=phone, school=school, gender=result[0][2], dob=result[0][3])


@app.route('/logout')
def logout():
    session['email'] = None
    return redirect(url_for('identify'))


@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    email = session['email']
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        username = request.form['Username']
        uploadedImage = request.files['profilePhoto']
        print(uploadedImage)
        imageBytes = uploadedImage.read()
        cur.execute('update user_profile set username=%s where email=%s', [
                    username, email])
        mysql.connection.commit()
        image = b64encode(imageBytes).decode('utf-8')
        if image != '':
            cur.execute(
                'update user_profile set photo=%s where email=%s', [image, email])
            mysql.connection.commit()
    cur.execute(
        'select photo, username from user_profile where email=%s', [email])
    result = cur.fetchall()
    cur.close()
    image = result[0][0].decode("utf-8")
    print("updated")
    return redirect(url_for('myProfile'))


@app.route('/profile/<email>')
def profile(email):
    myEmail = session['email']
    print(email, myEmail)
    cur = mysql.connection.cursor()
    cur.execute(
        'select photo, username, gender, dob from user_profile where email=%s', [email])
    result = cur.fetchall()
    cur.execute(
        'select * from friend_request where email1=%s and email2=%s', [email, myEmail])
    request1Status = cur.fetchall()
    cur.execute(
        'select * from friend_request where email1=%s and email2=%s', [myEmail, email])
    request2Status = cur.fetchall()
    cur.execute(
        'select * from friend_list where email1=%s and email2=%s', [email, myEmail])
    friendStatus = cur.fetchall()
    image = result[0][0].decode("utf-8")
    print(request1Status, request2Status, friendStatus)

    phone = []
    cur.execute('select phone_no from phone_numbers where email=%s', [email])
    results = cur.fetchall()
    print(results)
    for item in results:
        phone.append(item[0])
    school = []
    cur.execute('select school from schools where email=%s', [email])
    results = cur.fetchall()
    for item in results:
        school.append(item[0])

    posts = []
    cur.execute(
        'select username, image, text, likes, email, post_id,timestamp from post natural join user_profile where email = %s order by timestamp', [email])
    results = cur.fetchall()
    for post in results:
        temp_post = {}
        temp_post['username'] = post[0]
        temp_post['image'] = post[1].decode('utf-8')
        temp_post['text'] = post[2]
        temp_post['likes'] = post[3]
        temp_post['email'] = post[4]
        temp_post['post_id'] = post[5]
        print(post[6])
        temp_post['timestamp'] = datetime.fromtimestamp(
            post[6]).strftime('%d-%m-%Y %H:%M')

        posts.append(temp_post)

    cur.close()
    return render_template('profile.html', myEmail=myEmail, email=email, image=image, username=result[0][1],
                           request1Status=len(request1Status), request2Status=len(request2Status), friendStatus=len(friendStatus),
                           phone=phone, school=school, posts=posts, gender=result[0][2], dob=result[0][3])


@app.route('/send_friend_request', methods=['GET', 'POST'])
def send_friend_request():
    email1 = session['email']
    print(email1)
    email2 = request.form['email']
    friendStatus = request.form['friendStatus']
    request1Status = request.form['request1Status']
    request2Status = request.form['request2Status']
    print(email1, email2, friendStatus, request1Status, request2Status)
    print(type(int(friendStatus)))
    cur = mysql.connection.cursor()
    if int(request1Status) == 0 and int(friendStatus) == 0 and int(request2Status) == 0:
        cur.execute('insert into friend_request values(%s, %s)',
                    [email1, email2])
        mysql.connection.commit()
    elif int(request1Status) == 1:
        cur.execute('delete from friend_request where email1=%s and email2=%s', [
                    email2, email1])
        mysql.connection.commit()
        cur.execute('insert into friend_list values(%s, %s)', [email1, email2])
        mysql.connection.commit()
        cur.execute('insert into friend_list values(%s, %s)', [email2, email1])
        mysql.connection.commit()
    elif int(request2Status) == 1:
        cur.execute('delete from friend_request where email1=%s and email2=%s', [
                    email1, email2])
        mysql.connection.commit()
        cur.execute('insert into friend_list values(%s, %s)', [email1, email2])
        mysql.connection.commit()
        cur.execute('insert into friend_list values(%s, %s)', [email2, email1])
        mysql.connection.commit()
    cur.close()
    return redirect(url_for('profile', email=email2))


@app.route('/news_feed')
def news_feed():
    myEmail = session['email']
    print(myEmail)
    posts = []
    cur = mysql.connection.cursor()
    cur.execute(
        'select username, image, text, likes, email, post_id,timestamp from post natural join user_profile where email in (select email2 from friend_list where email1=%s) order by timestamp', [myEmail])
    results = cur.fetchall()
    for post in results:
        temp_post = {}
        temp_post['username'] = post[0]
        temp_post['image'] = post[1].decode('utf-8')
        temp_post['text'] = post[2]
        temp_post['likes'] = post[3]
        temp_post['email'] = post[4]
        temp_post['post_id'] = post[5]
        temp_post['timestamp'] = datetime.fromtimestamp(
            post[6]).strftime('%d-%m-%Y %H:%M')
        posts.append(temp_post)
    return render_template('news_feed.html', myEmail=myEmail, posts=posts)


@app.route('/update_likes', methods=['POST'])
def update_likes():
    myEmail = session['email']
    poster_email = request.form['poster_email']
    post_id = request.form['post_id']
    likes = request.form['likes']
    cur = mysql.connection.cursor()
    cur.execute('select * from likes where poster_email=%s and post_id=%s and liker_email=%s',
                [poster_email, int(post_id), myEmail])
    results = cur.fetchall()
    print('results:', results, len(results))
    if len(results) == 0:
        cur.execute('update post set likes=%s where email=%s and post_id=%s', [
                    int(likes)+1, poster_email, post_id])
        mysql.connection.commit()
        cur.execute('insert into likes values(%s, %s, %s)',
                    [poster_email, post_id, myEmail])
        mysql.connection.commit()
    else:
        cur.execute('update post set likes=%s where email=%s and post_id=%s', [
                    int(likes)-1, poster_email, post_id])
        mysql.connection.commit()
        cur.execute('delete from likes where poster_email=%s and post_id=%s and liker_email=%s', [
                    poster_email, post_id, myEmail])
        mysql.connection.commit()
    cur.close()
    return redirect(url_for('news_feed'))


@app.route('/upload_post', methods=['POST', 'GET'])
def upload_post():
    cur = mysql.connection.cursor()
    print(request.form)
    myEmail = session['email']
    cur.execute('select max(post_id) from post where email=%s', [myEmail])
    maxPostId = cur.fetchall()
    newPostId = 0
    if maxPostId[0][0] != None:
        newPostId = maxPostId[0][0] + 1
    image = request.files['image']
    imageBytes = image.read()
    text = request.form['text']
    cur.execute('call get_unix_timestamp()')
    current_timestamp = cur.fetchall()
    likes = 0
    if imageBytes != '':
        image64 = b64encode(imageBytes).decode('utf-8')
        cur.execute('insert into post values(%s, %s, %s, %s, %s, %s)', [
                    myEmail, newPostId, image64, text, current_timestamp, likes])
        mysql.connection.commit()
    else:
        cur.execute('insert into post values(%s, %d, %s, %s, %d, %d)', [
                    myEmail, newPostId, None, text, current_timestamp, likes])
        mysql.connection.commit()
    cur.close()
    return redirect(url_for('news_feed'))


@app.route('/search_profile', methods=['GET', 'POST'])
def search_profile():
    cur = mysql.connection.cursor()
    cur.execute('select email,username from user_profile')
    results = cur.fetchall()
    cur.close()
    return jsonify(results)


@app.route('/search_results', methods=['GET', 'POST'])
def search_results():
    myEmail = session['email']
    print(myEmail)
    username = request.form['username']
    cur = mysql.connection.cursor()
    cur.execute('select email,username,photo from user_profile where username like concat(\"%%\",%s,\"%%\")', [username])
    results = cur.fetchall()
    cur.close()
    user_list = []
    for user in results:
        profile = {}
        profile['email'] = user[0]
        profile['username'] = user[1]
        profile['photo'] = user[2].decode("utf-8")
        user_list.append(profile)
    return render_template('display_profiles.html', myEmail=myEmail, profiles=user_list)


@app.route('/chat/<email>', methods=['POST'])
def chat(email):
    myEmail = session['email']
    print(myEmail + ' - ' + email)
    cur = mysql.connection.cursor()
    cur.execute(
        'select username, photo from user_profile where email=%s', [email])
    res = cur.fetchall()
    username = res[0][0]
    photo = res[0][1].decode('utf-8')

    cur.execute(
        'select username, photo from user_profile where email=%s', [myEmail])
    res1 = cur.fetchall()
    myPhoto = res1[0][1].decode('utf-8')

    message_sent = request.form['message_to_send']
    print('message:' + message_sent + ";")
    cur.execute('call get_unix_timestamp()')
    current_timestamp = cur.fetchall()
    print(current_timestamp)
    if message_sent != '':
        cur.execute('insert into chat values(%s, %s, %s, %s)', [
                    myEmail, email, message_sent, current_timestamp[0][0]])
        mysql.connection.commit()
        cur.close()
    cur.execute(
        'select email2, username, photo from friend_list inner join user_profile on email2=email where email1=%s', [myEmail])
    res = cur.fetchall()
    friends = []
    for item in res:
        temp_friend = {}
        temp_friend['email'] = item[0]
        temp_friend['username'] = item[1]
        temp_friend['photo'] = item[2].decode('utf-8')
        friends.append(temp_friend)

    # fetching messages for chat
    messages = []
    if email == myEmail:
        pass
    else:
        cur.execute('select * from chat where (email1=%s and email2=%s) or (email1=%s and email2=%s) order by timestamp',
                    [myEmail, email, email, myEmail])
        res = cur.fetchall()
        for item in res:
            temp_message = {}
            temp_message['email1'] = item[0]
            temp_message['email2'] = item[1]
            temp_message['text'] = item[2]
            temp_message['timestamp'] = datetime.fromtimestamp(
                item[3]).strftime('%Y-%m-%d %H:%M:%S')
            messages.append(temp_message)
    print(friends)
    return render_template('chat.html', myPhoto=myPhoto, myEmail=myEmail, friends=friends, messages=messages, email=email, username=username, photo=photo)



@socketio.on('email', namespace='/private')
def receive_username(email):
    users[email] = request.sid
    print('email added!')


@socketio.on('private_message', namespace='/private')
def private_message(payload):
    recipient_session_id = users[payload['email']]
    message = payload['message']
    print(recipient_session_id, message)
    cur = mysql.connection.cursor()
    myEmail = session['email']
    cur.execute('call get_unix_timestamp()')
    current_timestamp = cur.fetchall()
    cur.execute('insert into chat values(%s,%s,%s,%s)', [
                myEmail, payload['email'], message, current_timestamp[0][0]])
    mysql.connection.commit()
    cur.close()
    emit('new_private_message', message,
         room=recipient_session_id, include_self=True)


@app.route('/admin_login')
def admin_login():
    return render_template('admin_login.html')


@app.route('/verify_admin', methods=['GET', 'POST'])
def verify_admin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['pass']
        passwordhash = hashlib.md5(password.encode()).hexdigest()
        cur = mysql.connection.cursor()
        cur.execute('select * from admin_credentials where email=%s', [email])
        result = cur.fetchall()  # fetch all entries which satisfied the query
        cur.close()
        session['email'] = email
        return redirect(url_for('admin_feed'))
    return


@app.route('/admin_feed')
def admin_feed():
    myEmail = session['email']
    print(myEmail)
    posts = []
    cur = mysql.connection.cursor()
    cur.execute(
        'select username, image, text, likes, email, post_id, timestamp from post natural join user_profile order by timestamp')
    results = cur.fetchall()
    for post in results:
        temp_post = {}
        temp_post['username'] = post[0]
        temp_post['image'] = post[1].decode('utf-8')
        temp_post['text'] = post[2]
        temp_post['likes'] = post[3]
        temp_post['email'] = post[4]
        temp_post['post_id'] = post[5]
        temp_post['timestamp'] = datetime.fromtimestamp(
            post[6]).strftime('%d-%m-%Y %H:%M')
        posts.append(temp_post)
        print(posts)
    return render_template('admin_feed.html', myEmail=myEmail, posts=posts)


@app.route('/delete_posts', methods=['POST'])
def delete_posts():
    post_id = request.form['post_id']
    email = request.form['poster_email']
    cur = mysql.connection.cursor()
    cur.execute('delete from post where email=%s and post_id=%s',
                [email, post_id])
    mysql.connection.commit()
    cur.execute('delete from likes where poster_email=%s and post_id=%s', [
                email, post_id])
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('admin_feed'))


if __name__ == '__main__':

    app.secret_key = 'acquaintance'
    app.config['SESSION_TYPE'] = 'filesystem'

    socketio.run(app, debug=True)
