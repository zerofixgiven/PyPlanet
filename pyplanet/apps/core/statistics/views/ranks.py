from pyplanet.views.generics import ManualListView
from .base import StatsView


class TopRanksView(ManualListView):
	title = 'Top ranked players on the server'
	icon_style = 'Icons128x128_1'
	icon_substyle = 'Statistics'

	def __init__(self, app, player, top_ranks):
		"""
		Init topsums list view.

		:param player: Player instance.
		:param app: App instance.
		:type player: pyplanet.apps.core.maniaplanet.models.Player
		:type app: pyplanet.apps.core.statistics.Statistics
		"""
		super().__init__(self)

		self.app = app
		self.player = player
		self.manager = app.context.ui
		self.provide_search = False
		self.top_ranks = top_ranks

	async def get_data(self):
		data = list()
		for idx, rank in enumerate(self.top_ranks):
			data.append(dict(
				rank=idx+1,
				player_nickname=rank.player.nickname,
				average='{:0.2f}'.format((rank.average / 10000))
			))

		return data

	async def destroy(self):
		self.top_ranks = None
		await super().destroy()

	def destroy_sync(self):
		self.top_ranks = None
		super().destroy_sync()

	async def get_fields(self):
		return [
			{
				'name': '#',
				'index': 'rank',
				'sorting': False,
				'searching': False,
				'width': 10,
				'type': 'label'
			},
			{
				'name': 'Player',
				'index': 'player_nickname',
				'sorting': False,
				'searching': False,
				'width': 80,
				'type': 'label'
			},
			{
				'name': 'Average',
				'index': 'average',
				'sorting': False,
				'searching': False,
				'width': 25,
				'type': 'label'
			}
		]
