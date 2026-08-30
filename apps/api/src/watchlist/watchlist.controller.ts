import { Controller, Get, Post, Delete, Body, Param, UseGuards, Req } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { PrismaService } from '../prisma/prisma.service';

@Controller('watchlist')
@UseGuards(AuthGuard('jwt'))
export class WatchlistController {
  constructor(private readonly prisma: PrismaService) {}

  @Get()
  async getWatchlist(@Req() req: any) {
    return this.prisma.watchlistItem.findMany({
      where: { userId: req.user.id },
      orderBy: { createdAt: 'desc' },
    });
  }

  @Post()
  async addToWatchlist(@Body() body: any, @Req() req: any) {
    return this.prisma.watchlistItem.create({
      data: {
        userId: req.user.id,
        ebayItemId: body.ebayItemId,
        ebayTitle: body.ebayTitle,
        ebayPrice: body.ebayPrice,
        ebayMarketplace: body.ebayMarketplace,
        supplierProductId: body.supplierProductId,
        supplierTitle: body.supplierTitle,
        supplierCost: body.supplierCost,
        matchScore: body.matchScore,
        netProfit: body.netProfit,
        margin: body.margin,
        roi: body.roi,
        recommendation: body.recommendation,
        notes: body.notes,
      },
    });
  }

  @Delete(':id')
  async removeFromWatchlist(@Param('id') id: string, @Req() req: any) {
    return this.prisma.watchlistItem.deleteMany({
      where: {
        id,
        userId: req.user.id, // Enforce tenant boundaries
      },
    });
  }
}