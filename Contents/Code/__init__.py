# Audiobooks (Audible)
# coding: utf-8
import re, types, traceback
import urllib
import Queue
import json
import os

#from mutagen import File
#from mutagen.mp4 import MP4
#from mutagen.id3 import ID3
#from mutagen.flac import FLAC
#from mutagen.flac import Picture
#from mutagen.oggvorbis import OggVorbis

remove_inv_json_esc=re.compile(r'([^\\])(\\(?![bfnrt\'\"\\/]|u[A-Fa-f0-9]{4}))' )
def json_decode(output):
  try:
    return json.loads(remove_inv_json_esc.sub(r'\1\\\2', output), strict=False)
  except ValueError as e:
    Log('Error decoding {0} {1}'.format(output, e))
    return None

# URLs
VERSION_NO = '1.2017.03.05.1'

REQUEST_DELAY = 0       # Delay used when requesting HTML, may be good to have to prevent being banned from the site

INITIAL_SCORE = 100     # Starting value for score before deductions are taken.
GOOD_SCORE = 98         # Score required to short-circuit matching and stop searching.
IGNORE_SCORE = 45       # Any score lower than this will be ignored.

THREAD_MAX = 20

intl_sites={
    'en' : { 'url': None                , 'rel_date' : u'Release Date'         , 'nar_by' : u'Narrated By'   , 'nar_by2': u'Narrated by'},
    'au' : { 'url': 'www.audible.com.au', 'rel_date' : u'Release Date'         , 'nar_by' : u'Narrated By'   , 'nar_by2': u'Narrated by'},
    'fr' : { 'url': 'www.audible.fr'    , 'rel_date' : u'Date de publication'  , 'nar_by' : u'Narrateur(s)'  , 'nar_by2': u'Lu par'},
    'de' : { 'url': 'www.audible.de'    , 'rel_date' : u'Erscheinungsdatum'    , 'nar_by' : u'Gesprochen von', 'rel_date2': u'Veröffentlicht'},
    'it' : { 'url': 'www.audible.it'    , 'rel_date' : u'Data di Pubblicazione', 'nar_by' : u'Narratore'     },
    'jp' : { 'url': 'www.audible.co.jp' , 'rel_date' : u'N/A', 'nar_by' : u'ナレーター'     }, # untested
    }


#https://www.amazon.com/s/ref=nb_sb_noss_2?url=search-alias%3Dstripbooks&field-keywords=Mistress+of+All+Evil%3A+A+Tale+of+the+Dark+Fairy
#https://www.amazon.com/s/ref=sr_nr_p_n_feature_browse-b_0?fst=as%3Aoff&rh=n%3A283155%2Ck%3AMistress%2Cp_n_feature_browse-bin%3A1240885011&keywords=Mistress&ie=UTF8&qid=1512920937&rnid=618072011
def SetupUrls(base, lang='en'):
    ctx=dict()
    if base is None:
        base='www.audible.com'
    if lang not in intl_sites :
        lang='en'

    if intl_sites[lang]['url'] is not None:
        base=intl_sites[lang]['url']
    ctx['REL_DATE']=intl_sites[lang]['rel_date']
    ctx['NAR_BY'  ]=intl_sites[lang]['nar_by']
    if 'rel_date2' in intl_sites[lang]:
        ctx['REL_DATE_INFO']=intl_sites[lang]['rel_date2']
    else:
        ctx['REL_DATE_INFO']=ctx['REL_DATE']
    if 'nar_by2' in intl_sites[lang]:
        ctx['NAR_BY_INFO' ]=intl_sites[lang]['nar_by2']
    else:
        ctx['NAR_BY_INFO' ]=ctx['NAR_BY'  ]

    AUD_BASE_URL='https://' + base + '/'
    ctx['AUD_BOOK_INFO'         ]=AUD_BASE_URL + 'pd/%s?ipRedirectOverride=true'
    ctx['AUD_ARTIST_SEARCH_URL' ]=AUD_BASE_URL + 'search?searchAuthor=%s&ipRedirectOverride=true'
    ctx['AUD_ALBUM_SEARCH_URL'  ]=AUD_BASE_URL + 'search?searchTitle=%s&x=41&ipRedirectOverride=true'
    ctx['AUD_KEYWORD_SEARCH_URL']=AUD_BASE_URL + 'search?filterby=field-keywords&advsearchKeywords=%s&x=41&ipRedirectOverride=true'
    ctx['AUD_SEARCH_URL'        ]=AUD_BASE_URL + 'search?searchTitle={0}&searchAuthor={1}&x=41&ipRedirectOverride=true'
    return ctx


def Start():
    #HTTP.ClearCache()
    HTTP.CacheTime = CACHE_1WEEK
    HTTP.Headers['User-agent'] = 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.2; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0)'
    HTTP.Headers['Accept-Encoding'] = 'gzip'
    

class AudiobookArtist(Agent.Artist):
    name = 'Audiobooks'
    languages = [Locale.Language.English, 'de', 'fr', 'it']
    primary_provider = True
    accepts_from = ['com.plexapp.agents.localmedia']

    prev_search_provider = 0
    

    def Log(self, message, *args):
        if Prefs['debug']:
            Log(message, *args)

    def getDateFromString(self, string):
        try:
            return Datetime.ParseDate(string).date()
        except:
            return None

    def getStringContentFromXPath(self, source, query):
        return source.xpath('string(' + query + ')')

    def getAnchorUrlFromXPath(self, source, query):
        anchor = source.xpath(query)

        if len(anchor) == 0:
            return None

        return anchor[0].get('href')

    def getImageUrlFromXPath(self, source, query):
        img = source.xpath(query)

        if len(img) == 0:
            return None

        return img[0].get('src')

    def findDateInTitle(self, title):
        result = re.search(r'(\d+-\d+-\d+)', title)
        if result is not None:
            return Datetime.ParseDate(result.group(0)).date()
        return None

    def doSearch(self, url, ctx):
    
      
        
        html = HTML.ElementFromURL(url, sleep=REQUEST_DELAY)

        found = []
        for r in html.xpath('//div[a/img[@class="yborder"]]'):
            date = self.getDateFromString(self.getStringContentFromXPath(r, 'text()[1]'))
            title = self.getStringContentFromXPath(r, 'a[2]')
            murl = self.getAnchorUrlFromXPath(r, 'a[2]')
            thumb = self.getImageUrlFromXPath(r, 'a/img')

            found.append({'url': murl, 'title': title, 'date': date, 'thumb': thumb})

        return found

    def search(self, results, media, lang, manual=False):
    
        # Author data is pulling from last.fm automatically.
        # This will probably never be built out unless a good
        # author source is identified.
    
    
        #Log some stuff
        self.Log('---------------------------------ARTIST SEARCH--------------------------------------------------')
        self.Log('* Album:           %s', media.album)
        self.Log('* Artist:           %s', media.artist)
        self.Log('****************************************Not Ready For Artist Search Yet*************************')
        self.Log('------------------------------------------------------------------------------------------------')	
        return
    
        
    def update(self, metadata, media, lang, force=False):
        return

    def hasProxy(self):
        return Prefs['imageproxyurl'] is not None

    def makeProxyUrl(self, url, referer):
        return Prefs['imageproxyurl'] + ('?url=%s&referer=%s' % (url, referer))

    def worker(self, queue, stoprequest):
        while not stoprequest.isSet():
            try:
                func, args, kargs = queue.get(True, 0.05)
                try: func(*args, **kargs)
                except Exception, e: self.Log(e)
                queue.task_done()
            except Queue.Empty:
                continue

    def addTask(self, queue, func, *args, **kargs):
        queue.put((func, args, kargs))

   


    


    

class AudiobookAlbum(Agent.Album):
    name = 'Audiobooks'
    languages = [Locale.Language.English, 'de', 'fr', 'it']
    primary_provider = True
    accepts_from = ['com.plexapp.agents.localmedia']

    prev_search_provider = 0
    
    
    def Log(self, message, *args):
        if Prefs['debug']:
            Log(message, *args)

    def getDateFromString(self, string):
        try:
            return Datetime.ParseDate(string).date()
        except:
            return None

    def getStringContentFromXPath(self, source, query):
        return source.xpath('string(' + query + ')')

    def getAnchorUrlFromXPath(self, source, query):
        anchor = source.xpath(query)

        if len(anchor) == 0:
            return None

        return anchor[0].get('href')

    def getImageUrlFromXPath(self, source, query):
        img = source.xpath(query)

        if len(img) == 0:
            return None

        return img[0].get('src')

    def findDateInTitle(self, title):
        result = re.search(r'(\d+-\d+-\d+)', title)
        if result is not None:
            return Datetime.ParseDate(result.group(0)).date()
        return None

    def doSearch(self, url, ctx):
        found = []
        try:
            html = HTML.ElementFromURL(url, sleep=REQUEST_DELAY)
        
            for r in html.xpath('//div[contains (@class, "adbl-search-result")]'):
                date = self.getDateFromString(self.getStringContentFromXPath(r, 'div/div/ul/li[contains (., "{0}")]/span[2]//text()'.format(ctx['REL_DATE']).decode('utf-8')))
                #title = self.getStringContentFromXPath(r, 'div[contains (@class,"adbl-prod-meta-data-cont")]/div[contains (@class,"adbl-prod-title")]/a[1]')
                title = self.getStringContentFromXPath(r, 'div/div/div/div/a[1]')
                #murl = self.getAnchorUrlFromXPath(r, 'div[contains (@class,"adbl-prod-meta-data-cont")]/div[contains (@class,"adbl-prod-title")]/a[1]')
                murl = self.getAnchorUrlFromXPath(r, 'div/div/div/div/a[1]')
                thumb = self.getImageUrlFromXPath(r, 'div[contains (@class,"adbl-prod-image-sample-cont")]/a/img')
                author = self.getStringContentFromXPath(r, 'div/div/ul/li//a[contains (@class,"author-profile-link")][1]')
                narrator = self.getStringContentFromXPath(r, 'div/div/ul/li[contains (., "{0}")]//a[1]'.format(ctx['NAR_BY']).decode('utf-8'))
                self.Log('---------------------------------------XPATH SEARCH HIT-----------------------------------------------')
                
                found.append({'url': murl, 'title': title, 'date': date, 'thumb': thumb, 'author': author, 'narrator': narrator})

        except NetworkError:
            pass

        return found

    def search(self, results, media, lang, manual):
        ctx=SetupUrls(Prefs['site'], lang)
        LCL_IGNORE_SCORE=IGNORE_SCORE
        
        self.Log('---------------------------------------ALBUM SEARCH-----------------------------------------------')
        self.Log('* ID:              %s', media.parent_metadata.id)
        self.Log('* Title:           %s', media.title)
        self.Log('* Name:            %s', media.name)
        self.Log('* Album:           %s', media.album)
        self.Log('* Artist:          %s', media.artist)
        self.Log('--------------------------------------------------------------------------------------------------')	
    
        # Handle a couple of edge cases where album search will give bad results.
        if media.album is None and not manual:
          return	  
        if media.album == '[Unknown Album]' and not manual:
          return	
        
        if media.filename is not None:
          Log('Filename search: %s', urllib.unquote(media.filename))
          Log('Album search: %s', media.album)
        else:
          # If this is a custom search, use the user-entered name instead of the scanner hint.
          Log('Custom album search for: {0} {1}'.format(media.name, media.album) )
          media.title = media.name
          media.album = media.name

        # Log some stuff for troubleshooting detail
        self.Log('-----------------------------------------------------------------------')
        self.Log('* ID:              %s', media.parent_metadata.id)
        self.Log('* Title:           %s', media.title)
        self.Log('* Name:            %s', media.name)
        self.Log('* Name:            %s', media.album)
        self.Log('-----------------------------------------------------------------------')
        
        # Normalize the name
        normalizedName = String.StripDiacritics(media.album)
        if len(normalizedName) == 0:
            normalizedName = media.album

        # Chop off "unabridged"
        normalizedName = re.sub(r"[\(\[].*?[\)\]]", "", normalizedName)
        normalizedName = normalizedName.strip()

        self.Log('***** SEARCHING FOR "%s" - AUDIBLE v.%s *****', normalizedName, VERSION_NO)

        # Make the URL
        match = False
        found = None
        if media.filename is not None:
            filename=os.path.basename(urllib.unquote(media.filename))
            match = re.search(Prefs['id_regex'], filename, re.IGNORECASE)
            if match :
                self.Log('id_regex  : %s', str(Prefs['id_regex']))
                self.Log('filename  : %s', str(filename))
                self.Log('audible_id: %s', str(match.group('audibleid')))
                found=self.get_data(match.group('audibleid'), lang)
                self.Log('found     : %s', str(found))
        if not match:  ###metadata id provided
            match = re.search("(?P<book_title>.*?)\[(?P<source>(audible))-(?P<audibleid>B[a-zA-Z0-9]{9,9})\]", media.title, re.IGNORECASE)
            if match :
                found=self.get_data(match.group('audibleid'), lang)
        if found is None:
            if match:  ###metadata id provided
                searchUrl = ctx['AUD_KEYWORD_SEARCH_URL'] % (String.Quote((match.group('audibleid')).encode('utf-8'), usePlus=True))
                LCL_IGNORE_SCORE=0
            elif media.artist is not None:
                nm=String.Quote((normalizedName).encode('utf-8'), usePlus=True)
                ma=String.Quote((media.artist  ).encode('utf-8'), usePlus=True)
                searchUrl = ctx['AUD_SEARCH_URL'].format(nm, ma)
            else:
                searchUrl = ctx['AUD_ALBUM_SEARCH_URL'] % (String.Quote((normalizedName).encode('utf-8'), usePlus=True))
                found = self.doSearch(searchUrl, ctx)
        else:
            found = [found]
            LCL_IGNORE_SCORE=0
        #found2 = media.album.lstrip('0123456789')
        #if normalizedName != found2:
        #    searchUrl = D18_SEARCH_URL % (String.Quote((found2).encode('utf-8'), usePlus=True))
        #    found.extend(self.doSearch(searchUrl))

        # Write search result status to log
        if found is None or len(found) == 0:
            self.Log('No results found for query "%s"', normalizedName)
            return
        else:
            self.Log('Found %s result(s) for query "%s"', len(found), normalizedName)
            i = 1
            for f in found:
                self.Log('    {0}. (title) {1} (url)[{2}] (date)({3}) (thumb){4}'.format(i, f['title'], f['url'], str(f['date']), f['thumb']))
                i += 1

        self.Log('-----------------------------------------------------------------------')
        # Walk the found items and gather extended information
        info = []
        i = 1
        for f in found:
            url = f['url']
            self.Log('URL For Breakdown: %s', url)
            #if re.search(r'http://www\.audible\.com', url) is None:
            #    self.Log('re.search is None')
            #    continue

            # Get the id
            for itemId in url.split('/') :
                if re.match(r'B0[0-9A-Z]{8,8}', itemId):
                    #Log('Match: %s', itemId)
                    itemId=re.sub(r'\?.*', r'', itemId)
                    break
                itemId=None

            if len(itemId) == 0:
                Log('No Match: %s', url)
                continue

            self.Log('* ID is                 %s', itemId)

            title    = f['title']
            thumb    = f['thumb']
            date     = f['date']
            year     = ''
            author   = f['author']
            narrator = f['narrator']

            if date is not None:
                year = date.year

            # Score the album name
            scorebase1 = media.album
            scorebase2 = title.encode('utf-8')
            #self.Log('scorebase1:    %s', scorebase1)
            #self.Log('scorebase2:    %s', scorebase2)

            score = INITIAL_SCORE - Util.LevenshteinDistance(scorebase1, scorebase2)

            if media.artist:
              scorebase3 = media.artist
              scorebase4 = author
              #self.Log('scorebase3:    %s', scorebase3)
              #self.Log('scorebase4:    %s', scorebase4)
              score = INITIAL_SCORE - Util.LevenshteinDistance(scorebase3, scorebase4)
              
            
            #if metadata.originally_available_at:
            #    scorebase1 += ' (' + metadata.originally_available_at + ')'
            #    scorebase2 += ' (' + str(year) + ')'

            #score = INITIAL_SCORE

            self.Log('* Title is              %s', title)
            self.Log('* Author is             %s', author)
            self.Log('* Narrator is           %s', narrator)
            self.Log('* Date is               %s', str(date))
            self.Log('* Score is              %s', str(score))
            self.Log('* Thumb is              %s', thumb)

            if score >= LCL_IGNORE_SCORE:
                info.append({'id': itemId, 'title': title, 'year': year, 'date': date, 'score': score, 'thumb': thumb, 'artist' : author})
            else:
                self.Log('# Score is below ignore boundary (%s)... Skipping!', LCL_IGNORE_SCORE)

            if i != len(found):
                self.Log('-----------------------------------------------------------------------')

            i += 1

        info = sorted(info, key=lambda inf: inf['score'], reverse=True)

        # Output the final results.
        self.Log('***********************************************************************')
        self.Log('Final result:')
        i = 1
        for r in info:
            self.Log('    [%s]    %s. %s (%s) %s {%s} [%s]', r['score'], i, r['title'], r['year'], r['artist'], r['id'], r['thumb'])
            results.Append(MetadataSearchResult(id = r['id'], name  = r['title'], score = r['score'], thumb = r['thumb'], lang = lang))

            # If there are more than one result, and this one has a score that is >= GOOD SCORE, then ignore the rest of the results
            if not manual and len(info) > 1 and r['score'] >= GOOD_SCORE:
                self.Log('            *** The score for these results are great, so we will use them, and ignore the rest. ***')
                break
            i += 1

    def get_data(self, aid, lang):
        data=dict()
        ctx=SetupUrls(Prefs['site'], lang)
        
        # Make url
        url = ctx['AUD_BOOK_INFO'] % aid

        Log('url: {0}'.format(url))
        try:
            html = HTML.ElementFromURL(url, cacheTime = 0, follow_redirects=True, sleep=REQUEST_DELAY)
        except : #NetworkError
            return None
            pass
        #Log('HHH {0}'.format(data))
        
        date    =None
        series  =''
        genre1  =None
        genre2  =None
        synopsis=None
        for r in html.xpath('//div[contains (@id, "adbl_page_content")]'):
            date     = self.getDateFromString(self.getStringContentFromXPath(r, '//li[contains (., "{0}")]/span[2]//text()'.format(ctx['REL_DATE_INFO']).decode('utf-8')))
            #title   = self.getStringContentFromXPath(r, 'div[contains (@class,"adbl-prod-meta-data-cont")]/div[contains (@class,"adbl-prod-title")]/a[1]')
            title    = self.getStringContentFromXPath(r, '//h1[contains (@class, "adbl-prod-h1-title")]/text()')
            murl     = self.getAnchorUrlFromXPath(r, 'div/div/div/div/a[1]')
            thumb    = self.getImageUrlFromXPath(r, 'div/div/div/div/div/img')
            author   = self.getStringContentFromXPath(r, '//li//a[contains (@class,"author-profile-link")][1]')
            narrator = self.getStringContentFromXPath(r, '//li[contains (., "{0}")]//span[2]'.format(ctx['NAR_BY_INFO'])).strip().decode('utf-8')
            studio   = self.getStringContentFromXPath(r, '//li//a[contains (@id,"PublisherSearchLink")][1]')
            synopsis = self.getStringContentFromXPath(r, '//div[contains (@class, "disc-summary")]/div[*]').strip()
            series   = self.getStringContentFromXPath(r, '//div[contains (@class, "adbl-series-link")]//a[1]')
            genre1   = self.getStringContentFromXPath(r,'//div[contains(@class,"adbl-pd-breadcrumb")]/div[2]/a/span/text()')
            genre2   = self.getStringContentFromXPath(r,'//div[contains(@class,"adbl-pd-breadcrumb")]/div[3]/a/span/text()')
            self.Log('---------------------------------------XPATH SEARCH HIT-----------------------------------------------')

        if date is None :
            for r in html.xpath('//script[contains (@type, "application/ld+json")]'):
                json_data=json_decode(r.text_content())
                if json_data is None:
                    continue
                #Log('HHH {0}'.format(json_data))
                for json_data in json_data:
                    if 'datePublished' in json_data:
                        #for key in json_data:
                        #    Log('{0}:{1}'.format(key, json_data[key]))
                        date =self.getDateFromString(json_data['datePublished'])
                        title=json_data['name']
                        thumb=json_data['image']
                        author=''
                        counter=0
                        for c in json_data['author'] :
                            counter+=1
                            if counter > 1 :  
                                author+=', '
                            author+=c['name']
                        narrator=''
                        counter=0
                        for c in json_data['readBy'] :
                            counter+=1
                            if counter > 1 :  
                                narrator+=','
                            narrator+=c['name']
                        studio=json_data['publisher']
                        synopsis=json_data['description']
                    if 'itemListElement' in json_data:
                        #for key in json_data:
                        #    Log('{0}:{1}'.format(key, json_data[key]))
                        genre1=json_data['itemListElement'][1]['item']['name']
                        genre2=json_data['itemListElement'][2]['item']['name']
            
            for r in html.xpath('//li[contains (@class, "seriesLabel")]'):
                series = self.getStringContentFromXPath(r, '//li[contains (@class, "seriesLabel")]//a[1]')
                #Log(series.strip())
        # We need: 
        # Genre Tags
        # XXStudio
        # XXRelease Date
        # XXSeries Info (if Any)
        # XXSimilar authors? (fulled from last.fm)
        # XXSynopsis as review?
        # XXBigger album cover
        
		
        #cleanup synopsis
        if date is None:
            return None

        synopsis = synopsis.replace("<i>", "")
        synopsis = synopsis.replace("</i>", "")
        synopsis = synopsis.replace("<u>", "")
        synopsis = synopsis.replace("</u>", "")
        synopsis = synopsis.replace("<b>", "")
        synopsis = synopsis.replace("</b>", "")
        synopsis = synopsis.replace("<br />", "")
        synopsis = synopsis.replace("<p>", "")
        synopsis = synopsis.replace("</p>", "\n")
		
		
        self.Log('date:        %s', date)
        self.Log('title:       %s', title)
        self.Log('author:      %s', author)
        self.Log('series:      %s', series)
        self.Log('narrator:    %s', narrator)
        self.Log('studio:      %s', studio)
        self.Log('thumb:       %s', thumb)
        self.Log('genres:      %s, %s', genre1, genre2)
        self.Log('synopsis:    %s', synopsis)
        data['url']     =url
        data['date']    =date
        data['title']   =title
        data['author']  =author
        data['series']  =series
        data['narrator']=narrator
        data['studio']  =studio
        data['thumb']   =thumb
        data['genre1']  =genre1
        data['genre2']  =genre2
        data['synopsis']=synopsis
        return data

    def update(self, metadata, media, lang, force=False):
        Log('***** UPDATING "%s" ID: %s - AUDIBLE v.%s *****', media.title, metadata.id, VERSION_NO)

        data=self.get_data(metadata.id, lang)

        if data is None:
            return None
        
        Log('HHH {0}'.format(data))
        
        # Set the date and year if found.
        if data['date'] is not None:
          metadata.originally_available_at = data['date']

        # Add the genres
        metadata.genres.clear()
        metadata.genres.add(data['series'].strip())
        for c in data['narrator'].split(','):
            metadata.genres.add(c.strip())
        metadata.genres.add(data['genre1'].strip())
        metadata.genres.add(data['genre2'].strip())

        metadata.producers.clear()
        for c in data['narrator'].split(','):
            metadata.producers.add(c.strip())
        
        # other metadata
        metadata.title = data['title']
        metadata.studio = data['studio']
        metadata.summary = data['synopsis']
        metadata.posters[1] = Proxy.Media(HTTP.Request(data['thumb']))
        metadata.posters.validate_keys(data['thumb'])

        metadata.title = data['title']
        media.artist = data['author']

        self.writeInfo('New data', data['url'], metadata)

    def hasProxy(self):
        return Prefs['imageproxyurl'] is not None

    def makeProxyUrl(self, url, referer):
        return Prefs['imageproxyurl'] + ('?url=%s&referer=%s' % (url, referer))

    def worker(self, queue, stoprequest):
        while not stoprequest.isSet():
            try:
                func, args, kargs = queue.get(True, 0.05)
                try: func(*args, **kargs)
                except Exception, e: self.Log(e)
                queue.task_done()
            except Queue.Empty:
                continue

    def addTask(self, queue, func, *args, **kargs):
        queue.put((func, args, kargs))

   
    

    ### Writes metadata information to log.
    def writeInfo(self, header, url, metadata):
        self.Log(header)
        self.Log('-----------------------------------------------------------------------')
        self.Log('* ID:              %s', metadata.id)
        self.Log('* URL:             %s', url)
        self.Log('* Title:           %s', metadata.title)
        self.Log('* Release date:    %s', str(metadata.originally_available_at))
        self.Log('* Studio:          %s', metadata.studio)
        self.Log('* Summary:         %s', metadata.summary)

        if len(metadata.collections) > 0:
            self.Log('|\\')
            for i in range(len(metadata.collections)):
                self.Log('| * Collection:    %s', metadata.collections[i])

        if len(metadata.genres) > 0:
            self.Log('|\\')
            for i in range(len(metadata.genres)):
                self.Log('| * Genre:         %s', metadata.genres[i])

        if len(metadata.posters) > 0:
            self.Log('|\\')
            for poster in metadata.posters.keys():
                self.Log('| * Poster URL:    %s', poster)

        if len(metadata.art) > 0:
            self.Log('|\\')
            for art in metadata.art.keys():
                self.Log('| * Fan art URL:   %s', art)

        self.Log('***********************************************************************')

def safe_unicode(s, encoding='utf-8'):
    if s is None:
        return None
    if isinstance(s, basestring):
        if isinstance(s, types.UnicodeType):
            return s
        else:
            return s.decode(encoding)
    else:
        return str(s).decode(encoding)
