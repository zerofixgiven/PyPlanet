import logging

from pyplanet.apps.config import AppConfig

from pyplanet.contrib.setting import Setting
from pyplanet.apps.core.maniaplanet import callbacks as mp_signals
from pyplanet.contrib.map.exceptions import ModeIncompatible
from pyplanet.utils.times import format_time
from pyplanet.utils.style import STRIP_ALL, style_strip

logger = logging.getLogger(__name__)

class DynatimeApp(AppConfig):

	game_dependencies = ['trackmania', 'trackmania_next']

	mode_dependencies = ['TimeAttack']

	app_dependencies = ['core.maniaplanet']

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.setting_dynatime_active = Setting(
			'dynatime_active', 'Dynatime Active', Setting.CAT_BEHAVIOUR, type=bool,
			description='Activate Dynamic Round timer based on map medal time',
			default=False
		)

		self.setting_dynatime_announce = Setting(
			'dynatime_accounce', 'Dynatime Announce', Setting.CAT_BEHAVIOUR, type=bool,
			description='Announce the current timelimit at the start of each round',
			default=True
		)

		self.setting_dynatime_medal = Setting(
			'dynatime_medal', 'Dynatime Medal', Setting.CAT_BEHAVIOUR, type=int,
			description='Set medal to determine map time (0: bronze, 1: silver, 2: gold, 3: author)',
			default=3
		)

		self.setting_dynatime_multiplier = Setting(
			'dynatime_multiplier', 'Dynatime Multiplier', Setting.CAT_BEHAVIOUR, type=int,
			description='Multiply map time by this amount to get round timer',
			default=4
		)

		self.setting_dynatime_minimum_time = Setting(
			'dynatime_minimum_time', 'Dynatime Minimum Time', Setting.CAT_BEHAVIOUR, type=int,
			description='Define minimum timelimit',
			default=180
		)

		self.setting_dynatime_maximum_time = Setting(
			'dynatime_maximum_time', 'Dynatime Maximum Time', Setting.CAT_BEHAVIOUR, type=int,
			description='Define maximum timelimit',
			default=600
		)

		self.setting_dynatime_minimum_time_is_offset = Setting(
			'dynatime_minimum_time_is_offset', 'Dynatime Minimum Time Is Offset', Setting.CAT_BEHAVIOUR, type=bool,
			description='Use minimum time as an offset to the dynamic timelimit instead as a minimum timelimit',
			default=True
		)

		self.setting_dynatime_round_time = Setting(
			'dynatime_round_time', 'Dynatime Round time', Setting.CAT_BEHAVIOUR, type=int,
			description='Round timelimit to closest (0: off 1-30: valid)',
			default=15
		)

	async def on_init(self):
		await super().on_init()

	async def on_start(self):
		await super().on_start()

		await self.context.setting.register(
			self.setting_dynatime_active,
			self.setting_dynatime_announce,
			self.setting_dynatime_medal,
			self.setting_dynatime_multiplier,
			self.setting_dynatime_minimum_time,
			self.setting_dynatime_maximum_time,
			self.setting_dynatime_minimum_time_is_offset,
			self.setting_dynatime_round_time
		)

		self.context.signals.listen(mp_signals.map.map_begin, self.on_map_begin)

	async def on_stop(self):
		await super().on_stop()

	async def on_destroy(self):
		await super().on_destroy()

	async def on_map_begin(self, map, **kwargs):
		is_active  = await self.setting_dynatime_active.get_value()

		if not is_active:
			return

		clip = lambda x, l, u: l if x < l else u if x > u else x

		medal = clip(await self.setting_dynatime_medal.get_value(refresh=True), 0, 3)
		multiplier = await self.setting_dynatime_multiplier.get_value(refresh=True)
		min_time = max(await self.setting_dynatime_minimum_time.get_value(refresh=True), 0)
		max_time = max(await self.setting_dynatime_maximum_time.get_value(refresh=True), 0)
		is_offset = await self.setting_dynatime_minimum_time_is_offset.get_value(refresh=True)
		roundto = clip(await self.setting_dynatime_round_time.get_value(refresh=True), 0, 30)
		
		mode_settings = await self.instance.mode_manager.get_settings()

		if 'S_TimeLimit' not in mode_settings:
			raise ModeIncompatible('Current mode doesn\'t support Dynatime. Not TimeAttack?')

		medals = ['bronze', 'silver', 'gold', 'author']
		medal_time = eval('map.time_{0}'.format(medals[medal]))
		if map.num_laps > 0:
			medal_time /= map.num_laps

		timelimit = (min_time if is_offset else 0) + int(multiplier * medal_time / 1000)
		if timelimit < min_time and not is_offset:
			timelimit = min_time
		if timelimit > max_time > min_time:
			timelimit = max_time
		if roundto > 0:
			timelimit = timelimit // 60 * 60 + roundto * ((timelimit % 60 // roundto) + (1 if ((timelimit % 60) % roundto) / roundto >= 0.5 else 0))
		timelimit_ms = timelimit * 1000;

		mode_settings['S_TimeLimit'] = timelimit

		mname = style_strip( map.name, STRIP_ALL)
		new_time = format_time( time=timelimit_ms, hide_milliseconds=True)
		bm_time = format_time( time=medal_time, hide_milliseconds=True)
		chat_message = '$ff0Set timelimit for $fff{0}$ff0 to $fff⏳ {1}$ff0.'.format( mname, new_time )
		#chat_message = '$ff0Dynatime set new timelimit for map $fff{0}$ff0 to $fff⏳ {1}$ff0, based on the {2}-medal of $fff🏆 {3}'.format( mname, new_time, medals[medal], bm_time )

		await self.instance.mode_manager.update_settings(mode_settings)

		announce = await self.setting_dynatime_announce.get_value()
		if announce:
			await self.instance.chat(chat_message)
