import sys
sys.path.append('C:/Users/A/Google Drive/Reddit/Reddit Bots/ActiveBots')
from UniversalFunctions import *
sys.path.append('')
import random

class Record(object):

    def __init__(self, submission, connection):
        # I'm immediately grabbing the submission and holding it in my object so I don't need to ping reddit.
        self.submission = submission
        self.submission_id = self.submission.fullname
        self.created_utc = int(self.submission.created_utc)
        self.recorded_utc = time.time()
        self.selftext = self.submission.selftext.lower()
        self.author = self.submission.author
        self.karma = self.author.comment_karma + self.author.link_karma
        self.subreddit = self.submission.subreddit
        self.connection = connection
        self.cursor = self.connection.cursor()
        
    def CompileOptions(self): # We organize our options
        # print('CompileOptions', self.submission_id)
        self.SampleOptions = set()
        self.optionsForExplanation = "" # We'll need this when we write the reply.
        Options = re.findall(r'!(\w+)',self.selftext)
        for option in Options:
            if option.lower() != 'pollbot' and not(any(option.lower() == thing for thing in self.SampleOptions)):
                self.SampleOptions.add(option.lower())
                self.optionsForExplanation = self.optionsForExplanation + "* " + option.lower() + "\n"
        
    def RecordRequestedPoll(self):
        # print('RecordRequestedPoll', self.submission_id)
        CheckingRecord = self.cursor.execute('SELECT ROWID FROM Polls WHERE submission_id=?',(self.submission_id,))
        CheckedRecord = CheckingRecord.fetchall()
        if len(CheckedRecord) == 0 and ('!pollbot' in self.selftext):
            self.CompileOptions()
            if len(self.SampleOptions) > 1: # Confirm we actually have options.
                # Note the find in SQL.
                self.cursor.execute('INSERT OR IGNORE INTO Polls (submission_id, created_utc, recorded_utc) VALUES (?,?,?)', (self.submission_id, self.created_utc, self.recorded_utc))
                self.connection.commit()
                # And tell everyone how to react to our bot.
                self.submission.reply("Hello, I am a pollbot. I was summoned by the author, or original poster (OP), of this post. I am here to help OP quickly check the pulse of reddit. Here's how it works:\n\nOP summoned me with the phrase *!PollBot*, and then followed that key phrase with the options for this poll. For this poll, the options are:\n\n" + self.optionsForExplanation + "\nTo demonstrate your support for a particular position, include one of the phrases, such as *!" + random.sample(self.SampleOptions,1)[0] + "* in your comment, including the exclamation point.\n\nAfter 24 hours, I will return to post a summary of the results.\n\nPlease note that I only count your vote if you have at least 100 karma, and earned at least 5 karma in this subreddit in the last 60 days; or if you are an approved submitter in this subreddit. You are allowed one vote per submission.\n\n*This bot is maintained by u/sjrsimac.*")
    
    def VoterCheck(self, Botname,  RequiredEarnedScoreOverLastSixtyDaysToVote):
        # print('VoterCheck', self.submission_id)
        RecentScoreInSubreddit = 0
        for comment in self.author.comments.new(limit=1000):
            if comment.created_utc >= time.time() - 5184000 and comment.subreddit == self.subreddit:
                RecentScoreInSubreddit = RecentScoreInSubreddit + comment.score
                if RecentScoreInSubreddit >= RequiredEarnedScoreOverLastSixtyDaysToVote:
                    break
        for submission in self.author.submissions.new(limit=1000):
            if submission.created_utc >= time.time() - 5184000 and submission.subreddit == self.subreddit:
                RecentScoreInSubreddit = RecentScoreInSubreddit + submission.score
                if RecentScoreInSubreddit >= RequiredEarnedScoreOverLastSixtyDaysToVote:
                    break
        for moderator in self.subreddit.moderator():
            if moderator == Botname and (moderator.mod_permissions == ['all'] or any('access' == permission for permission in moderator.mod_permissions)):
                for approved_submitter in self.subreddit.contributor():
                    if author.name == approved_submitter: # This automatically grants all approved submitters the ability to vote.
                        karma = 100
                        RecentScoreInSubreddit = RequiredEarnedScoreOverLastSixtyDaysToVote
                        break
                break
        if self.karma >= 100 and RecentScoreInSubreddit >= RequiredEarnedScoreOverLastSixtyDaysToVote:
            return True
        else:
            return False
    
    def ConductPoll(self, Botname, RequiredEarnedScoreOverLastSixtyDaysToVote):
        # print('ConductPoll', self.submission_id)
        self.CompileOptions()
        VoteCounter = {}
        AlreadyVoted = set()
        for option in self.SampleOptions:
            VoteCounter[option] = 0
        self.submission.comments.replace_more()
        for comment in self.submission.comments.list():
            Votes = re.findall(r'!(\w+)',comment.body)
            if len(Votes) == 1 and self.VoterCheck(Botname, RequiredEarnedScoreOverLastSixtyDaysToVote) and not(any(comment.author == hasvoted for hasvoted in AlreadyVoted)) and any(Votes[0] == option for option in self.SampleOptions):
                VoteCounter[Votes[0]] += 1
                AlreadyVoted.add(comment.author)
        Header = ""
        Separator = ""
        Counts = ""
        for result in VoteCounter:
            Header = Header + result + "|"
            Separator = Separator + ":---:|" * len(VoteCounter)
            Counts = Counts + str(VoteCounter[result]) + "|"
        Header = Header[0:len(Header)-1]
        Separator = Separator[0:len(Separator)-1]
        Counts = Counts[0:len(Counts)-1]
        if len(Header + "\n" + Separator + "\n" + Counts) <= 10000:
            self.submission.reply(Header + "\n" + Separator + "\n" + Counts)
        self.cursor.execute('UPDATE Polls SET counted_utc=? WHERE submission_id=?',(time.time(), self.submission_id))
        self.connection.commit()

def PollMain(Botname, OurSubreddits, Database):
    reddit = StartingTheBot(Botname)
    
    RequiredEarnedScoreOverLastSixtyDaysToVote = 0

    # This is where you begin the connection to the SQLite database and prepare the cursor.
    connection = sqlite3.connect(Database)
    cursor = connection.cursor()
    # cursor.execute('CREATE TABLE Polls (submission_id text PRIMARY KEY, created_utc int, recorded_utc float, counted_utc float)') # This line stays commented unless you're making a new database.
    connection.commit()
    
    for submission in reddit.subreddit(OurSubreddits).new(limit=100):
        CurrentRecord = Record(submission, connection)
        # print(CurrentRecord.submission_id)
        CurrentRecord.RecordRequestedPoll()

    CheckReadyForCounting = cursor.execute('SELECT submission_id FROM Polls WHERE counted_utc is NULL and created_utc<=?', (time.time()-86400,))
    ReadyForCounting = CheckReadyForCounting.fetchall()
    for submission_id in ReadyForCounting:
        CurrentRecord = Record(reddit.submission(id=submission_id[0][3:]), connection)
        CurrentRecord.ConductPoll(Botname,  RequiredEarnedScoreOverLastSixtyDaysToVote)

    connection.close()
        
if __name__ == '__main__':
    start = time.time()
    PollMain('pollthecrowd','pollthecrowdsandbox','C:/Users/A/Google Drive/Reddit/Reddit Bots/PollBot/Polls.db')
    print((time.time()-start)/60)