from django.shortcuts import redirect, render

NEWS = [
    {
        'id': 1,
        'title': 'Feux de forêt maîtrisés dans les Landes',
        'source': 'Mongabay',
        'country': 'France',
        'date': 'il y a 4 h',
        'link': 'https://news.mongabay.com/',
    },
    {
        'id': 2,
        'title': "L'Indonésie annonce un vaste plan de reforestation",
        'source': 'Mongabay',
        'country': 'Monde',
        'date': 'il y a 1 j',
        'link': 'https://news.mongabay.com/',
    },
]


def news_list(request):
    return render(request, 'news/list.html', {'news' : NEWS})


def news_detail(request, pk):
    news = next((n for n in NEWS if n['id'] == pk), None)
    return render(request, 'news/detail.html', {'news': news})


def news_read(request, pk):
    news = next((n for n in NEWS if n['id'] == pk), None)
    # Plus tard : incrémenter le compteur de clics avant de rediriger.
    return redirect(news['link'] if news else 'news:list')