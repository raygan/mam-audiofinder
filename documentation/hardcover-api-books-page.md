Fields
Field	Type	Description
compilation	bool	
release_year	int	
rating	float	
pages	int	
users_count	int32	
lists_count	int32	
ratings_count	int32	
reviews_count	int32	
author_names	string[]	
cover_color	auto	
genres	string[]	
moods	string[]	
content_warnings	string[]	
tags	string[]	
series_names	string[]	
has_audiobook	bool	
has_ebook	bool	
contribution_types	string[]	
slug	string	
title	string	
description	string	
subtitle	string	
release_date	date	
audio_seconds	auto	
users_read_count	int32	
prompts_count	int32	
activities_count	int32	
release_date_i	auto	
featured_book_series	book_series	
featured_series_id	int	
alternative_titles	string[]	
isbns	string[]	
contributions	contributions[]	
image	auto	
book_category_id	int	
book_characters	Characters	
book_mappings	book_mappings[]	
book_series	book_series[]	
book_status	book_statuses	
canonical	Books	
canonical_id	int	
created_at	timestamp	
created_by_user_id	int	
default_audio_edition	Editions	
default_audio_edition_id	int	
default_cover_edition	Editions	
default_cover_edition_id	int	
default_ebook_edition	Editions	
default_ebook_edition_id	int	
default_physical_edition	Editions	
default_physical_edition_id	int	
dto	string[]	
dto_combined	string[]	
dto_external	string[]	
editions	Editions	
editions_count	int	
header_image_id	int	
headline	string	
id	int	
image	images[]	
import_platform_id	int	
journals_count	int	
links	string[]	
list_books	list_books[]	
literary_type_id	int	
locked	bool	
prompt_answers	prompt_answers[]	
prompt_summaries	prompt_books_summary[]	
ratings_distribution	string[]	
recommendations	recommendations[]	
state	string	
taggable_counts	taggable_counts[]	
taggings	taggings[]	
updated_at	timestamptz	
user_added	bool	
user_books	user_books[]	
User Book Statuses
Status	Description
1	Want to Read
2	Currently Reading
3	Read
4	Paused
5	Did Not Finished
6	Ignored
Get a List of Books in a User’s Library
Query
Try it yourself


Run query
Success!

Results
{
  "user_books": []
}
Get a List of Books by a Specific Author
Query
Try it yourself
Books by User Count
query BooksByUserCount {
    books(
          where: {
              contributions: {
                  author: {
                      name: {_eq: "Brandon Sanderson"}
                  }
              }
          }
          limit: 10
          order_by: {users_count: desc}
    ) {
          pages
          title
          id
    }
}

Getting All Editions of a Book
Query
Try it yourself


Run query
Success!

Results
{
  "editions": [
    {
      "id": 32096109,
      "title": "Oathbringer",
      "edition_format": "",
      "pages": 1248,
      "release_date": "2017-11-14",
      "isbn_10": null,
      "isbn_13": "9781473226012",
      "publisher": {
        "name": "Stormlight Archive"
      }
    },
    {
      "id": 30491539,
      "title": "Oathbringer",
      "edition_format": "Mass Market Paperback",
      "pages": 1298,
      "release_date": "2019-09-01",
      "isbn_10": "0765365294",
      "isbn_13": "9780765365293",
      "publisher": {
        "name": "Tor Fantasy"
      }
    },
    {
      "id": 30805990,
      "title": "Oathbringer",
      "edition_format": "Audiobook",
      "pages": null,
      "release_date": "2017-11-14",
      "isbn_10": null,
      "isbn_13": "9781427275936",
      "publisher": {
        "name": "Macmillan Audio"
      }
    },
    {
      "id": 31725904,
      "title": "Oathbringer",
      "edition_format": "Audiobook",
      "pages": null,
      "release_date": "2017-11-14",
      "isbn_10": "1427275947",
      "isbn_13": "9781427275943",
      "publisher": {
        "name": "Macmillan Audio"
      }
    },
    {
      "id": 30615153,
      "title": "Oathbringer",
      "edition_format": "Audio CD",
      "pages": null,
      "release_date": "2017-11-14",
      "isbn_10": "1427275920",
      "isbn_13": "9781427275929",
      "publisher": {
        "name": "Macmillan Audio"
      }
    },
    {
      "id": 32230410,
      "title": "Oathbringer",
      "edition_format": "Kindle",
      "pages": null,
      "release_date": "2017-11-16",
      "isbn_10": null,
      "isbn_13": null,
      "publisher": {
        "name": "Orion Publishing Group"
      }
    },
    {
      "id": 32220998,
      "title": "Oathbringer",
      "edition_format": null,
      "pages": null,
      "release_date": null,
      "isbn_10": null,
      "isbn_13": "9781648813825",
      "publisher": null
    },
    {
      "id": 32221006,
      "title": "Oathbringer",
      "edition_format": "Audiobook",
      "pages": null,
      "release_date": null,
      "isbn_10": null,
      "isbn_13": "9781648813801",
      "publisher": {
        "name": "GraphicAudio"
      }
    },
    {
      "id": 32221027,
      "title": "Oathbringer",
      "edition_format": "Audiobook",
      "pages": null,
      "release_date": null,
      "isbn_10": null,
      "isbn_13": "9781648813863",
      "publisher": {
        "name": "Graphic Audio"
      }
    },
    {
      "id": 32221014,
      "title": "Oathbringer",
      "edition_format": null,
      "pages": null,
      "release_date": null,
      "isbn_10": null,
      "isbn_13": "9781648813849",
      "publisher": null
    },
    {
      "id": 32221007,
      "title": "Oathbringer",
      "edition_format": "Audiobook",
      "pages": null,
      "release_date": null,
      "isbn_10": null,
      "isbn_13": "9781648813887",
      "publisher": {
        "name": "Graphic Audio"
      }
    },
    {
      "id": 31766046,
      "title": "Oathbringer",
      "edition_format": "Audible",
      "pages": null,
      "release_date": "2017-11-14",
      "isbn_10": null,
      "isbn_13": null,
      "publisher": {
        "name": "Macmillan Audio"
      }
    },
    {
      "id": 31675791,
      "title": "Oathbringer",
      "edition_format": null,
      "pages": null,
      "release_date": null,
      "isbn_10": null,
      "isbn_13": null,
      "publisher": null
    },
    {
      "id": 32170429,
      "title": "Oathbringer",
      "edition_format": "Audio CD",
      "pages": null,
      "release_date": null,
      "isbn_10": "1628517522",
      "isbn_13": "9781628517521",
      "publisher": {
        "name": "Graphic Audio"
      }
    },
    {
      "id": 32170431,
      "title": "Oathbringer",
      "edition_format": "Audiobook",
      "pages": null,
      "release_date": null,
      "isbn_10": "1628517336",
      "isbn_13": "9781628517330",
      "publisher": {
        "name": "Graphic Audio"
      }
    },
    {
      "id": 32170430,
      "title": "Oathbringer",
      "edition_format": "Audio CD",
      "pages": null,
      "release_date": null,
      "isbn_10": "1628517395",
      "isbn_13": "9781628517392",
      "publisher": {
        "name": "Graphic Audio"
      }
    },
    {
      "id": 32044934,
      "title": "Oathbringer",
      "edition_format": null,
      "pages": 1389,
      "release_date": null,
      "isbn_10": null,
      "isbn_13": null,
      "publisher": null
    },
    {
      "id": 32201431,
      "title": "Oathbringer",
      "edition_format": "",
      "pages": 1243,
      "release_date": "2017-11-01",
      "isbn_10": "1250169496",
      "isbn_13": "9781250169495",
      "publisher": {
        "name": "Tor Romance"
      }
    },
    {
      "id": 31780792,
      "title": "Oathbringer",
      "edition_format": "Paperback",
      "pages": 1408,
      "release_date": "2017-11-14",
      "isbn_10": null,
      "isbn_13": "9781399622080",
      "publisher": {
        "name": "Orion Publishing Group, Limited"
      }
    },
    {
      "id": 31812803,
      "title": "Oathbringer",
      "edition_format": "Audio CD",
      "pages": null,
      "release_date": null,
      "isbn_10": "1628517166",
      "isbn_13": "9781628517163",
      "publisher": {
        "name": "Graphic Audio"
      }
    },
    {
      "id": 31812807,
      "title": "Oathbringer",
      "edition_format": "Audiobook",
      "pages": null,
      "release_date": null,
      "isbn_10": "1628517123",
      "isbn_13": "9781628517125",
      "publisher": {
        "name": "Graphic Audio"
      }
    },
    {
      "id": 31450041,
      "title": "Oathbringer",
      "edition_format": "Kindle",
      "pages": 1220,
      "release_date": "2017-11-14",
      "isbn_10": null,
      "isbn_13": null,
      "publisher": {
        "name": "Tor Books"
      }
    },
    {
      "id": 31230963,
      "title": "Oathbringer",
      "edition_format": "ebook",
      "pages": 1227,
      "release_date": "2017-11-14",
      "isbn_10": "0575093358",
      "isbn_13": "9780575093355",
      "publisher": {
        "name": "Hachette UK"
      }
    },
    {
      "id": 32170434,
      "title": "Oathbringer",
      "edition_format": "Audiobook",
      "pages": null,
      "release_date": null,
      "isbn_10": "1628517255",
      "isbn_13": "9781628517255",
      "publisher": {
        "name": "GraphicAudio"
      }
    },
    {
      "id": 21953653,
      "title": "Oathbringer",
      "edition_format": "Hardcover",
      "pages": 1233,
      "release_date": "2017-11-14",
      "isbn_10": "1250297141",
      "isbn_13": "9781250297143",
      "publisher": {
        "name": "Tor Books"
      }
    },
    {
      "id": 13195833,
      "title": "Oathbringer",
      "edition_format": null,
      "pages": null,
      "release_date": null,
      "isbn_10": null,
      "isbn_13": null,
      "publisher": null
    },
    {
      "id": 30395769,
      "title": "Oathbringer",
      "edition_format": "Paperback",
      "pages": 1243,
      "release_date": "2017-01-01",
      "isbn_10": "057509334X",
      "isbn_13": "9780575093348",
      "publisher": {
        "name": "Gollancz"
      }
    },
    {
      "id": 30616153,
      "title": "Oathbringer",
      "edition_format": "Audiobook",
      "pages": null,
      "release_date": "2017-11-14",
      "isbn_10": null,
      "isbn_13": "9781648813788",
      "publisher": {
        "name": "Graphic Audio"
      }
    },
    {
      "id": 30932402,
      "title": "Oathbringer",
      "edition_format": "",
      "pages": 1233,
      "release_date": "2017-01-01",
      "isbn_10": "0575093331",
      "isbn_13": "9780575093331",
      "publisher": {
        "name": "Gollancz"
      }
    },
    {
      "id": 30407773,
      "title": "Oathbringer",
      "edition_format": "",
      "pages": 1220,
      "release_date": "2017-11-14",
      "isbn_10": null,
      "isbn_13": null,
      "publisher": null
    },
    {
      "id": 30499832,
      "title": "Oathbringer",
      "edition_format": "Hardcover",
      "pages": 1242,
      "release_date": "2017-01-01",
      "isbn_10": "1250162165",
      "isbn_13": "9781250162168",
      "publisher": {
        "name": "Tor Books"
      }
    },
    {
      "id": 32187775,
      "title": "Oathbringer",
      "edition_format": "Kindle",
      "pages": 1220,
      "release_date": "2017-11-14",
      "isbn_10": null,
      "isbn_13": null,
      "publisher": null
    },
    {
      "id": 31614965,
      "title": "Oathbringer",
      "edition_format": null,
      "pages": 1220,
      "release_date": "2017-11-14",
      "isbn_10": "0765399830",
      "isbn_13": "9780765399830",
      "publisher": {
        "name": "Tor Books"
      }
    },
    {
      "id": 30455612,
      "title": "Oathbringer",
      "edition_format": "Hardcover",
      "pages": 1243,
      "release_date": "2017-11-14",
      "isbn_10": "076532637X",
      "isbn_13": "9780765326379",
      "publisher": {
        "name": "Tor Books"
      }
    },
    {
      "id": 32309394,
      "title": "Oathbringer",
      "edition_format": null,
      "pages": null,
      "release_date": null,
      "isbn_10": null,
      "isbn_13": null,
      "publisher": null
    }
  ]
}
Create a New Book
Query
Create Book
mutation {
    createBook(input: {
          title: "My First Book",
          pages: 300,
          release_date: "2024-09-07"
          description: "This is my first book."
      }) {
      book {
            title
            pages
            release_date
            description
      }
    }
}
